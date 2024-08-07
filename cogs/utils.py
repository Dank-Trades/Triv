import discord
from discord.ext import commands
import re
import pandas as pd
from discord.components import Button, ButtonStyle
import datetime as dt
import matplotlib.pyplot as plt
import io
import hashlib
import os
import statistics

class utils(commands.Cog):
    def __init__(self, client):
        self.client = client

    def compute_file_hash(self, filepath):
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def get_cogs_hashes(self):
        hashes = {}
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                filepath = os.path.join('./cogs', filename)
                hashes[filename] = self.compute_file_hash(filepath)
        return hashes

    
    async def send_error_message(self, msg, error_message):
        jump_url = msg.jump_url
        content = msg.content
        message = f"> {content}\n\n{error_message}"
        view = discord.ui.View()
        button = discord.ui.Button(label='Jump to message', url=jump_url, style=ButtonStyle.url)
        view.add_item(button)
        try:
            await msg.author.send(message, view=view)
        except discord.Forbidden:
            await msg.add_reaction('⚠')

    def extract_item_and_amount(self, text):
        pattern = r"(\d{1,3}(?:,\d{3})*|\d+)\s+<a?:(?:[a-zA-Z0-9_]+):[0-9]+>\s+([^\*]+)"
        match = re.search(pattern, text)
    
        if match:
            amount = match.group(1)
            item_name = match.group(2)
            return int(amount.replace(",", "")), item_name
        else:
            return None, None

    def process_shorthand(self, input_str):
        try:
            return float(input_str)
        except ValueError:
            pass

        shorthand_map = {
            'k': 1e3, 'm': 1e6, 'mil': 1e6, 'b': 1e9, 'bil': 1e9,
            't': 1e12, 'trillion': 1e12, 'million': 1e6, 'billion': 1e9
        }

        regex = r'^([+-]?[0-9]*\.?[0-9]+)([a-zA-Z]+)?$'
        match = re.match(regex, input_str)

        if not match:
            return 0

        numeric_part = match.group(1)
        shorthand_part = match.group(2)

        try:
            numeric_value = float(numeric_part)
        except ValueError:
            return 0

        if shorthand_part:
            shorthand_part = shorthand_part.lower()
            multiplier = shorthand_map.get(shorthand_part)
            if multiplier:
                return numeric_value * multiplier
            else:
                return 0

        return numeric_value
    
    def check_start_price(self, item: str, item_amount: int, price: int):
        data = pd.read_json('auctions.json')
        matching_items = data.loc[data['name'].str.lower().str.strip().str.match('^' + re.escape(item.strip().lower()) + '$'), 'price']
        
        if matching_items.empty:
            return 0  # or some other value or action if there are no matching items

        item_max_price = int(matching_items.values[0])


        max_price = item_max_price * item_amount
        
        if max_price <= 5e5:
            return max_price
        
        if price > 2e8 and price <= max_price :
            return 2e8

        if price > max_price:
            return max_price
        
        else:
            return 0


    async def bid(self, ctx, bid, min_increment):
        loop_cog = self.client.get_cog('loops')

        if loop_cog.auc_count.is_running():
            full_int = self.process_shorthand(bid)
            full_int = int(full_int)

            if self.client.first_bid[ctx.guild.id] == True:
                
                if full_int < float(self.client.start_price[ctx.channel.id]):
                    pass

                elif full_int >= float(self.client.start_price[ctx.channel.id]):
                    self.client.last_bids[ctx.channel.id] = []
                    self.client.last_bids[ctx.channel.id].append(full_int)
                    self.client.bidders[ctx.channel.id] = []
                    self.client.bidders[ctx.channel.id].append(ctx.author.id)


                    self.client.curr_bids[ctx.channel.id] = full_int
                    self.client.first_bid[ctx.guild.id] = False
                    await ctx.channel.send(f'{ctx.author.mention} bid **{format(full_int, ",")}**')

                    loop_cog.auc_count.restart()

            if self.client.first_bid[ctx.guild.id] == False:

                if full_int < float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                    pass
                
                elif full_int >= float(self.client.curr_bids[ctx.channel.id]) + min_increment:
                    self.client.last_bids[ctx.channel.id].append(full_int)
                    self.client.bidders[ctx.channel.id].append(ctx.author.id)
                    self.client.curr_bids[ctx.channel.id] = full_int
                    await ctx.channel.send(f'{ctx.author.mention} bid **{format(full_int, ",")}**')
                    loop_cog.auc_count.restart()
        else:
            try:
                await ctx.message.add_reaction('‼')
            except:
                pass
    
    async def update_user_roles(self, guild):
    # Fetch leaderboard data for each category
        data = await self.client.db.profile.find({'guild_id': guild.id}).to_list(length=None)

        leaderboard_data = {
            'bid amount': sorted(data, key=lambda x: x.get('total_amount_bid', 0), reverse=True)[:10],
            'auctions won': sorted(data, key=lambda x: x.get('auction_won', 0), reverse=True)[:10],
            'auctions joined': sorted(data, key=lambda x: x.get('auction_joined', 0), reverse=True)[:10],
            'auctions requested': sorted(data, key=lambda x: x.get('total_auction_requested', 0), reverse=True)[:10]
        }

        # Extract user IDs of the top 10 users from each category
        top_users = {category: [profile['user_id'] for profile in profiles] for category, profiles in leaderboard_data.items()}
        respective_roles = {'bid amount': 1233460981968142367, 'auctions won': 1233460999894335500,
                            'auctions joined': 1233460990121742367, 'auctions requested': 1233461091892199434}

        # Retrieve the role to assign
        # Replace role_id with the ID of the role to assign

        # Update roles for each category
        for category, user_ids in top_users.items():
            for user_id in user_ids:
                # Get the member object
                member = guild.get_member(user_id)
                if member:
                    # Check if the member already has the role
                    role_to_assign = guild.get_role(respective_roles[category])
                    if role_to_assign:
                        if role_to_assign not in member.roles:
                            # If not, add the role
                            await member.add_roles(role_to_assign)
                    else:
                        print(f"Role for category '{category}' not found.")
            # Remove the role from users not in the top 10
            for member in guild.members:
                for category, role_id in respective_roles.items():
                    role_to_check = guild.get_role(role_id)
                    if role_to_check and role_to_check in member.roles and member.id not in top_users[category]:
                        await member.remove_roles(role_to_check)

    

    async def get_auc_count(self, guild):
    
        daily = await self.client.db.auc_count.find_one({'guild_id' : guild.id, 
                                                        'year' : dt.datetime.utcnow().year, 
                                                        'month' : dt.datetime.utcnow().month, 
                                                        'day' : dt.datetime.utcnow().day})
        daily_count = daily.get('auc_count', 0)


        monthly = await self.client.db.auc_count.find({'guild_id' : guild.id, 
                                                    'year' : dt.datetime.utcnow().year, 
                                                    'month' : dt.datetime.utcnow().month}).to_list(length = None)
        
        monthly_count = sum([day['auc_count'] for day in monthly])

        current_date = dt.datetime.utcnow()
        start_of_week = current_date - dt.timedelta(days=current_date.weekday())
        end_of_week = start_of_week + dt.timedelta(days=7)

        weekly = await self.client.db.auc_count.find({'guild_id': guild.id,
                                                    'year': current_date.year,
                                                    'month': current_date.month,
                                                    'day': {'$gte': start_of_week.day, '$lt': end_of_week.day}}).to_list(None)
        
        weekly_count = sum(day['auc_count'] for day in weekly)

        return {'daily' : daily_count, 'monthly' : monthly_count, 'weekly' : weekly_count}
    
    async def update_user_count(self, guild, user, target):

        participants = await self.client.db.participants.find_one({'guild_id' : guild.id})
        if not participants:
            await self.client.db.participants.insert_one({'guild_id' : guild.id, 'queue_users' : {}, 'auction_users' : {}})
            participants = await self.client.db.participants.find_one({'guild_id' : guild.id})

        curr_time = dt.datetime.utcnow()
        user_count = participants[target]

        curr_date = str(curr_time.date())
        curr_hour = str(curr_time.hour)

        if curr_date not in user_count:
            user_count.update({curr_date : {}})

        if 'unique_users' not in user_count[curr_date]:
            user_count[curr_date].update({'unique_users' : []})
        
        if 'today_event_count' not in user_count[curr_date]:
            user_count[curr_date].update({'today_event_count' : 0})

        if curr_hour not in user_count[curr_date]:
            user_count[curr_date].update({curr_hour : []})

        curr_users = user_count[curr_date][curr_hour]
        unique_users = user_count[curr_date]['unique_users']


        if user.id not in curr_users:
            curr_users.append(user.id)
        if user.id not in unique_users:
            unique_users.append(user.id)      
        
        await self.client.db.participants.update_one({'guild_id' : guild.id} , {'$set' : {target : user_count}})



    async def get_user_count(self, guild, scope, target):

        participants = await self.client.db.participants.find_one({'guild_id' : guild.id})
        if not participants:
            return print('WARNING : No data found.')
        
        user_count = participants[target]
        event_count = 0

        timestamps = []
        values = []
        avg_user_count = 0
        unique_user_count = 0
        total_event_count = 0
        avg_event_count = 0


        if scope == 'today':
            curr_time = dt.datetime.utcnow()
            curr_date = str(curr_time.date())
            today_count = user_count[curr_date]
            unique_user_count = 0
            for key, value in today_count.items():
                if key == 'unique_users':
                    unique_user_count = len(value)
                    continue
                elif key == 'today_event_count' :
                    event_count += value
                    continue
                else :
                    timestamps.append(key)
                    values.append(len(value))
            avg_user_count = statistics.mean(values)
        
        elif scope == 'everyday':

            total_unique_users = []
            key_sums = {}
            for category in user_count.values():
                for key, value in category.items():
                    if key == 'unique_users':
                        for user in value:
                            if user not in total_unique_users:
                                total_unique_users.append(user)
                        continue
                    elif key == 'today_event_count' :
                        event_count += value
                        continue
                    else :
                        key_sums[key] = key_sums.get(key, 0) + len(value)

            unique_user_count = len(total_unique_users)
            key_sums = dict(sorted(key_sums.items(), key=lambda item: int(item[0])))
            timestamps, values = list(key_sums.keys()), list(key_sums.values())
            avg_user_count = statistics.mean(values)


        elif scope == 'overall':
            
            total_unique_users = []
            unique_user_count = 0
            total_values = {}
            for category, subcategories in user_count.items():
                total_category_values = 0
                for key, values in subcategories.items():
                    if key == 'unique_users':
                        total_category_values += len(values)
                        for user in values:
                            if user not in total_unique_users:
                                total_unique_users.append(user)
                    elif key == 'today_event_count':
                        event_count += values
                total_values[category] = total_category_values

            timestamps, values = list(total_values.keys()), list(total_values.values())
            avg_user_count = statistics.mean(values)
            unique_user_count = len(total_unique_users)


        elif scope == 'event_count':
            event_count = 0
            auc_count_everyday = {}
            for category, subcategories in user_count.items():
                for key, value in subcategories.items():
                    if key == 'today_event_count':
                        auc_count_everyday[category] = value
                        event_count += value
            timestamps, values = list(auc_count_everyday.keys()), list(auc_count_everyday.values())
            avg_event_count = statistics.mean(values)




        plt.figure(figsize=(10, 6))
        plt.style.use('dark_background')
        plt.plot(timestamps, values, marker='o')
        plt.title('Metrics')
        plt.xlabel('Time')
        plt.ylabel('User Count')
        plt.xticks(rotation=45)
        plt.grid(True)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        file = discord.File(buffer, filename='plot.png')


        return {'file' : file, 
                'avg_user_count' : round(avg_user_count),
                'unique_user_count' : unique_user_count, 
                'event_count' : event_count, 
                'average_event_count' : round(avg_event_count)
                }
    
    
    

    async def update_auc_stats(self, guild, user):
        auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        if not auctioneer_stats:
            await self.client.db.auctioneer_stats.insert_one({'guild_id' : guild.id, 'auc_stats' : {}})
            auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        
        auc_stats = auctioneer_stats['auc_stats']
        try :
            auctioneer = auc_stats[str(user.id)]
        except KeyError:
            auc_stats.update({str(user.id) : {
                'today' : 0,
                'weekly' : 0,
                'monthly': 0,
                'past_weekly' : 0,
                'past_monthly' : 0, 
                'total' : 0,
                'date' : str(dt.datetime.utcnow().date()),
                'week' : str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())),
                'month' : str(dt.datetime.utcnow().month)
            }})
            auctioneer = auc_stats[str(user.id)]

        if auctioneer['week'] != str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())):

            for auc in auc_stats.values():
                if auc['week'] != str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())):
                    auc.update({'past_weekly' : auc['weekly']})
                    auc.update({'week' : str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())), 'weekly' : 0})
                    auc.update({'date' : str(dt.datetime.utcnow().date()), 'today' : 0})


        
        if auctioneer['date'] != str(dt.datetime.utcnow().date()):
            for auc in auc_stats.values():
                if auc['date'] != str(dt.datetime.utcnow().date()):
                    auc.update({'date' : str(dt.datetime.utcnow().date()), 'today' : 0})

        if auctioneer['month'] != str(dt.datetime.utcnow().month):
            for auc in auc_stats.values():
                if auc['month'] != str(dt.datetime.utcnow().month):
                    auc.update({
                        'past_monthly' : auc['monthly'],
                        'monthly' : 0,
                        'month' : str(dt.datetime.utcnow().month)
                    })
        
        auctioneer = auc_stats[str(user.id)]

        
        auctioneer['today'] += 1
        auctioneer['weekly'] += 1
        auctioneer['monthly'] += 1
        auctioneer['total'] += 1

        auc_stats[str(user.id)] = auctioneer

        await self.client.db.auctioneer_stats.update_one({'guild_id' : guild.id}, {'$set' : {'auc_stats' : auc_stats}})



    async def get_auc_stats(self, guild, user):
        auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        if not auctioneer_stats:
            await self.client.db.auctioneer_stats.insert_one({'guild_id' : guild.id, 'auc_stats' : {}})
            auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        
        auc_stats = auctioneer_stats['auc_stats']
        try :
            auctioneer = auc_stats[str(user.id)]
        except KeyError:
            auc_stats.update({str(user.id) : {
                'today' : 0,
                'weekly' : 0,
                'monthly' : 0,
                'past_weekly' : 0,
                'past_monthly' : 0, 
                'total' : 0,
                'date' : str(dt.datetime.utcnow().date()),
                'week' : str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())),
                'month' : str(dt.datetime.utcnow().month)
            }})
            auctioneer = auc_stats[str(user.id)]
            
            if auctioneer['week'] != str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())):
                for auc in auc_stats.values():
                    if auc['week'] != str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())):
                        auc.update({'past_weekly' : auc['weekly']})
                        auc.update({'week' : str(dt.date.today() - dt.timedelta(days = dt.date.today().weekday())), 'weekly' : 0})
                        auc.update({'date' : str(dt.datetime.utcnow().date()), 'today' : 0})

            if auctioneer['date'] != str(dt.datetime.utcnow().date()):
                for auc in auc_stats.values():
                    if auc['date'] != str(dt.datetime.utcnow().date()):
                        auc.update({'date' : str(dt.datetime.utcnow().date()), 'today' : 0})

            auctioneer = auc_stats[str(user.id)]

        return {'today' : auctioneer['today'], 'weekly' : auctioneer['weekly'], 'total' : auctioneer['total'], 'past_weekly' : auctioneer['past_weekly'], 'monthly' : auctioneer['monthly'], 'past_monthly' : auctioneer['past_monthly']}
    


    async def get_leaderboard(self, guild, scope : str):
        
        auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        if not auctioneer_stats:
            await self.client.db.auctioneer_stats.insert_one({'guild_id' : guild.id, 'auc_stats' : {}})
            auctioneer_stats = await self.client.db.auctioneer_stats.find_one({'guild_id' : guild.id})
        
        auc_stats = auctioneer_stats['auc_stats']
        activity = {user_id: stats[scope] for user_id, stats in auc_stats.items()}
        sorted_users = dict(sorted(activity.items(), key=lambda x: x[1], reverse=True))

        return sorted_users
    



    async def get_auction_channel(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return arg.guild.get_channel(doc["auction_channel"])

    async def get_auctioneer_role(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["auctioneer_role"])

    async def get_auction_ping(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["ping_role"])

    async def get_auction_access(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["auction_access"])

    async def get_auction_log(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.channels, id=doc["auction_log"])

    async def get_tradeout_channel(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.channels, id=doc["tradeout_channel"])

    async def get_tradeout_role(self, arg):
        doc = await self.client.db.guild_config.find_one({"guild_id": arg.guild.id})
        if doc:
            return discord.utils.get(arg.guild.roles, id=doc["tradeout_role"])

    @staticmethod
    def channel_open(channel, role):
        overwrites = channel.overwrites_for(role)
        overwrites.send_messages = True
        # overwrites.read_messages = True
        return overwrites

    @staticmethod
    def channel_close(channel, role):
        overwrites = channel.overwrites_for(role)
        overwrites.send_messages = False
        # overwrites.read_messages = True
        return overwrites

    @staticmethod
    def tradeout_access(channel, member, set : bool):
        overwrites = channel.overwrites_for(member)
        overwrites.send_messages = set
        return overwrites



async def setup(client):
    await client.add_cog(utils(client))