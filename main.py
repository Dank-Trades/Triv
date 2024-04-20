import discord
import json
import os
import asyncpg
import asyncio
from discord import app_commands
from discord.ext import commands
from asyncpg.pool import create_pool
import motor.motor_asyncio

class Triv(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=['t!', '..'],
            intents=discord.Intents.all(),
            help_command= None
            )

    async def on_ready(self):
        etc = discord.Activity(type=discord.ActivityType.watching, name="over rey's miserable life")
        await client.change_presence(activity=etc)
        print('I\'m alive! ' + str(self.user.name))

    async def setup_hook(self):
        for file in os.listdir('./cogs'):
            if file.endswith('.py'):
                await self.load_extension(f'cogs.{file[:-3]}')
        await self.load_extension('jishaku')
        
        uri = 'mongodb+srv://dk2192002:LV9CQ9lqynd1Is1n@cluster0.vvdv1ec.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
        mongoclient = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = mongoclient['TrivDB']
        self.db.guild_config = self.db['guild_config']
        self.db.auction_queue = self.db['auction_queue']
        self.db.profile = self.db['profile']

        self.owner_id = 422967413295022080
        


with open('config.json', 'r') as f:
    data = json.load(f)
    token = data['TokeN']


client = Triv()


client.run(token)