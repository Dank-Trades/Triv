import discord
import json
import os
import asyncpg
from discord import app_commands
from discord.ext import commands
from asyncpg.pool import create_pool

class Triv(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='t!',
            intents=discord.Intents.all(),
            help_command= None,
            allowed_mentions = discord.AllowedMentions(roles=True, everyone=False, users=True)
            )

    async def on_ready(self):
        etc = discord.Activity(type=discord.ActivityType.watching, name="over rey's miserable life")
        await client.change_presence(activity=etc)
        print('I\'m alive!')

    async def setup_hook(self):
        for file in os.listdir('./cogs'):
            if file.endswith('.py'):
                await self.load_extension(f'cogs.{file[:-3]}')
        await self.load_extension('jishaku')
        with open('config.json', 'r')as f:
            data = json.load(f)
            _db = data['dAtabasE']
            _us = data['dB_useR']
            _pwd = data['dB_pwD']
        client.db = await asyncpg.create_pool(database = _db, user = _us, password = _pwd, host = '')
        await self.db.execute('CREATE TABLE IF NOT EXISTS guild_config (guild_id BIGINT NOT NULL, auction_channel BIGINT NOT NULL UNIQUE, auctioneer_role BIGINT NOT NULL, ping_role BIGINT NOT NULL, tradeout_role BIGINT NOT NULL, tradeout_channel BIGINT NOT NULL, auction_access BIGINT NOT NULL, auction_log BIGINT, min_increment DOUBLE PRECISION)')
        await self.db.execute('CREATE TABLE IF NOT EXISTS leaderboard (guild_id BIGINT NOT NULL, auctioneer TEXT NOT NULL, auctioneer_id BIGINT NOT NULL UNIQUE, auction_count BIGINT NOT NULL)')
        await self.db.execute('CREATE TABLE IF NOT EXISTS weekly_leaderboard (guild_id BIGINT NOT NULL, auctioneer TEXT NOT NULL, auctioneer_id BIGINT NOT NULL UNIQUE, auction_count BIGINT NOT NULL)')

        db = await self.db.fetchrow('SELECT * FROM "guild_config"')
        print(db)
        self.owner_id = 692994778136313896
        print(self.owner_ids)


with open('config.json', 'r') as f:
    data = json.load(f)
    token = data['TokeN']


client = Triv()


client.run(token)
