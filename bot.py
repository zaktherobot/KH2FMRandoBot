# bot.py
import io,zipfile,os,yaml
import json
from datetime import datetime, timedelta
import time, re
from dateutil import parser

def make_script_mod(script_name):
    return {"title":script_name,
                    "description": "See the lua for details",
                    "assets" : [{"name":"scripts/"+script_name,"method":"copy","source":[{"name":script_name}]}]}
def make_mod_yml(script_file,loaded_script):
    localfile = os.path.basename(script_file)
    script_name_zip = localfile.removesuffix(".lua") + ".zip"
    data = io.BytesIO()
    with zipfile.ZipFile(data,"w") as outZip:
        outZip.writestr(localfile,loaded_script)
        outZip.writestr("mod.yml", yaml.dump(make_script_mod(localfile), line_break="\r\n"))
        outZip.close()
    data.seek(0)
    return script_name_zip,data


import discord,logging
from discord.ext import commands,tasks
from dotenv import load_dotenv

def convert_to_discord_time(date_object):
    return "<t:"+str(int(time.mktime(date_object.timetuple())))+">"

def get_time_element(message,element):
    match_list = re.findall("[0-9]+ "+element, message)
    if len(match_list)>0:
        return int(re.findall("[0-9]+",match_list[0])[0])
    return 0

def get_reminder_offsets():
    return [timedelta(days=7),timedelta(days=1),timedelta(hours=2)]

class Reminder():
    def __init__(self,name,when,when_to_remind,where_to_remind):
        self.name = name
        self.when = when
        self.when_to_remind = when_to_remind
        self.where_to_remind = where_to_remind

    def __lt__(self,other):
        return self.when_to_remind < other.when_to_remind

    def __str__(self):
        return {"name":self.name,"when":self.when,"when_to_remind":self.when_to_remind,"where_to_remind":self.where_to_remind}

global reminder_queue
global reminder_json
reminder_queue = []
reminder_json = {"events":[]}

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='rando_bot.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix='!', description="Commands used for supporting KH2FM Rando", intents=intents)


def add_reminders(title,event_time,channel_id):
    for delta in get_reminder_offsets():
        reminder_object = event_time - delta
        if reminder_object > datetime.today(): # reminder is in the future
            reminder_queue.append(Reminder(title,event_time,reminder_object,channel_id))
        

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command()
async def emuhelp(ctx: commands.Context):
    """Help text for emulator rando"""
    response_text = ''' Hello! For PCSX2-EX, make sure it is 
    >>> - starting LuaEngine and loading scripts correctly. 
    - your ISO is clean
    - Run through openkh, check Show Console then about halfway down your looking for blue text `Initializing Lua Engine`. 
    - below that you should see it load your scripts and at the bottom you see `GSDx Lookup CRC: F266B00B` '''
    await ctx.channel.send(response_text)

@bot.command()
async def pchelp(ctx: commands.Context):
    """Help text for pc rando"""
    response_text = '''Hello! To help with debugging, please post 
    >>>- a screenshot of your KH install folder (the folder containing all the exe files, default folder is C:\Program Files (x86)\Epic Games)\n
    - a screenshot of your OpenKH Mod Manager (the program that you have installed the GoA Mod and your zip seed to)'''
    await ctx.channel.send(response_text)

@bot.command()
async def seedgen(ctx: commands.Context):
    """Link to the seed generator"""
    embed = discord.Embed()
    embed.description = "[Seed Generator](https://github.com/tommadness/KH2Randomizer/releases/latest/download/Kingdom.Hearts.II.Final.Mix.Randomizer.zip)"
    await ctx.channel.send(embed=embed)

@bot.command()
async def tracker(ctx: commands.Context):
    """Link to the tracker"""
    embed = discord.Embed()
    embed.description = "[KH2Tracker](https://github.com/Dee-Ayy/KH2Tracker/releases/latest/download/KhTracker.exe)"
    await ctx.channel.send(embed=embed)

@bot.command()
async def luamod(ctx: commands.Context):
    """Converts given lua files into an openkh mod"""
    attachments = ctx.message.attachments
    loaded_attachments = {}

    for a in attachments:
        if ".lua" in a.filename:
            attach_as_bytes = await a.read()
            loaded_attachments[a.filename] = attach_as_bytes.decode('utf8', 'strict')

    if len(loaded_attachments)>0:
        reply_files = []
        for key in loaded_attachments.keys():
            zip_name,zip_content = make_mod_yml(key,loaded_attachments[key])
            reply_files.append(discord.File(fp=zip_content,filename=zip_name))

        await ctx.channel.send(files=reply_files)
    else:
        await ctx.channel.send("No lua files found in message.")

@tasks.loop(minutes=1)
async def reminder_queue_process():
    if len(reminder_queue)>0:
        if reminder_queue[0].when_to_remind < datetime.today():
            message_channel = bot.get_channel(reminder_queue[0].where_to_remind)
            await message_channel.send(reminder_queue[0].name+" is happening at this time: "+convert_to_discord_time(reminder_queue[0].when))
            reminder_queue.pop(0)

@reminder_queue_process.before_loop
async def before():
    await bot.wait_until_ready()

@bot.listen()
async def on_ready():
    reminder_queue_process.start()

@bot.command()
async def reminder(ctx: commands.Context, title, *, message):
    """Queues reminders for a week, a day, and 2 hours before an event."""
    try:
        weeks = get_time_element(message,"weeks")
        days = get_time_element(message,"days")
        hours = get_time_element(message,"hours")
        minutes = get_time_element(message,"minutes")
        new_date_object = datetime.today() + timedelta(weeks=weeks,days=days,hours=hours,minutes=minutes)

        add_reminders(title,new_date_object,ctx.message.channel.id)

        reminder_json["events"]+={"event_title":title,
                                "event_time":str(new_date_object),
                                "event_channel":ctx.message.channel.id}
        
        with open("reminders.json", "w") as reminders_data:
            reminders_data.write(json.dumps(reminder_json))

        reminder_queue.sort()
        queue = ""
        for r in reminder_queue:
            queue+=convert_to_discord_time(r.when_to_remind)+"  "

        message_channel = bot.get_channel(ctx.message.channel.id)

        await message_channel.send(title + " happening at this time: " + convert_to_discord_time(new_date_object))


    except ValueError:
        await ctx.channel.send("Invalid time format")
    except OverflowError:
        await ctx.channel.send("Too far into the future...")

if os.path.exists("reminders.json"):
    # initialize reminders saved from earlier
    with open("reminders.json", "r") as reminders_data:
        reminder_json = json.loads(reminders_data.read())
        new_reminder_json = {"events":[]}

        # clean up any reminders that don't need to happen
        for reminder_data in reminder["events"]:
            event_time = parser.parse(reminder_data["event_time"])
            if event_time > datetime.today(): # event in the future
                add_reminders(reminder_data["event_title"],event_time,reminder_data["event_channel"])
                new_reminder_json["events"]+=reminder_data
        
        reminder_queue.sort()
        reminder_json = new_reminder_json

bot.run(TOKEN,log_handler=handler)