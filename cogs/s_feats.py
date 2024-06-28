import discord
from discord.ext import commands
from discord import app_commands

class s_feats(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.clowns = []
    
    def cog_check(self, ctx):
        return ctx.author.id in self.client.bot_mods


    @commands.command(name = 'clown')
    async def clown(self, ctx, user : discord.Member):
        if user.id not in self.client.clowns:
            await ctx.reply(f'{user.mention} is marked as a clown now. 🤡')
            self.client.clowns.append(user.id)
        else :
            await ctx.reply('They are marked as a clown already. 🤡')

    @commands.command(name= 'unclown')
    async def unclown(self, ctx, user : discord.Member):
        if user.id not in self.client.clowns:
            await ctx.reply(f'They are not marked as a clown yet.')
        else :
            self.client.clowns.remove(user.id)
            await ctx.reply(f'They are no longer a clown.')



    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.id not in self.client.clowns:
            return
        await msg.add_reaction('🤡')




async def setup(client):
    await client.add_cog(s_feats(client))