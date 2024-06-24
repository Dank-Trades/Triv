import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
from discord.app_commands import Group, command

class admin_utils(commands.Cog):
    def __init__(self, client):
        self.client = client

    def cog_check(self, ctx):
        return ctx.author.id == self.client.owner_id
    
    @commands.command()
    @commands.is_owner()  # Restrict command to bot owner
    async def exec(self, ctx, *, command):
        """Execute a terminal command."""
        try:
            # Run the command and capture the output
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            output = result.stdout if result.stdout else result.stderr
            
            # Limit output length to prevent excessive message length
            if len(output) > 2000:
                output = output[:1997] + '...'
            
            await ctx.send(f'```{output}```')
        except Exception as e:
            await ctx.send(f'Error: {e}')



async def setup(client):
    await client.add_cog(admin_utils(client))