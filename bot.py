# bot.py
import io,zipfile,os,yaml


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
from discord.ext import commands
from dotenv import load_dotenv

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

@bot.command()
async def response(ctx: commands.Context):
    await ctx.channel.send("Simple response")


bot.run(TOKEN,log_handler=handler)