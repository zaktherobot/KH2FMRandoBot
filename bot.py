# bot.py
import io,zipfile,os,yaml
from datetime import datetime, timedelta
import time, re, asyncio

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
reminder_queue = []

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='rando_bot.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True


bot = commands.Bot(command_prefix='!', description="Commands used for supporting KH2FM Rando", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


@bot.command()
async def luamod(ctx: commands.Context):
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
    try:
        weeks = get_time_element(message,"weeks")
        days = get_time_element(message,"days")
        hours = get_time_element(message,"hours")
        minutes = get_time_element(message,"minutes")
        new_date_object = datetime.today() + timedelta(weeks=weeks,days=days,hours=hours,minutes=minutes)

        for delta in get_reminder_offsets():
            reminder_object = new_date_object - delta
            # if reminder_object > datetime.today(): # reminder is in the future
            reminder_queue.append(Reminder(title,new_date_object,reminder_object,ctx.message.channel.id))
        
        reminder_queue.sort()
        queue = ""
        for r in reminder_queue:
            queue+=convert_to_discord_time(r.when_to_remind)+"  "

        message_channel = bot.get_channel(ctx.message.channel.id)

        await message_channel.send(title + " happening at this time: " + convert_to_discord_time(new_date_object) + " Queue: "+str(queue))


    except ValueError:
        await ctx.channel.send("Invalid time format")
    except OverflowError:
        await ctx.channel.send("Too far into the future...")

bot.run(TOKEN,log_handler=handler)