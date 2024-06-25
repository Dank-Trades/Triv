import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Group


class ConfirmButton(discord.ui.View):
    def __init__(self, client, author, opponent, interaction):
        super().__init__(timeout=10)
        self.client = client
        self.author = author
        self.opponent = opponent
        self.interaction = interaction

    def disable_buttons(self):
        for child in self.children:
            child.disabled = True
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.opponent
    
    async def on_timeout(self) -> None:
        self.disable_buttons()
        await self.interaction.edit_original_response(view=self)
        self.client.curr_players.pop(self.interaction.message.id, None)
        await self.interaction.followup.send("They didn't respond in time.", ephemeral=True)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.success)
    async def confirm_but(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.disable_buttons()
        await interaction.response.defer()
        self.client.curr_players[interaction.message.id].append(self.opponent.id)
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(f'{self.author.mention} is playing Tic-Tac-Toe with {self.opponent.mention}.\n{self.author.mention}\'s turn.', view=TicTacToeView(self.client, self.author, self.opponent))

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
    async def cancel_but(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.disable_buttons()
        await interaction.edit_original_response(view=self)
        self.client.curr_players.pop(interaction.message.id, None)
        await interaction.followup.send('Cancelled.', ephemeral=True)


class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(label='\u200b', style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if self.label != '\u200b' or interaction.user != view.current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        self.label = 'X' if view.current_player == view.player1 else 'O'
        self.style = discord.ButtonStyle.success if view.current_player == view.player1 else discord.ButtonStyle.danger
        self.disabled = True

        view.board[self.y][self.x] = self.label

        if view.current_player == view.player1:
            view.player1_moves.append(self)
            if len(view.player1_moves) > 3:
                first_move = view.player1_moves.pop(0)
                first_move.reset_button()
                view.board[first_move.y][first_move.x] = ''
        else:
            view.player2_moves.append(self)
            if len(view.player2_moves) > 3:
                first_move = view.player2_moves.pop(0)
                first_move.reset_button()
                view.board[first_move.y][first_move.x] = ''

        winner = view.check_winner()

        if winner or view.is_full():
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f'Game over! Winner: {view.current_player.mention}' if winner else 'Game over! It\'s a tie!', view=view)
            self.client.curr_players.pop(view.interaction.message.id, None)
        else:
            view.current_player = view.player2 if view.current_player == view.player1 else view.player1
            await interaction.response.edit_message(content=f'{view.current_player.mention}\'s turn', view=view)

    def reset_button(self):
        self.label = '\u200b'
        self.style = discord.ButtonStyle.secondary
        self.disabled = False


class TicTacToeView(discord.ui.View):
    def __init__(self, client, player1, player2):
        super().__init__(timeout=30)
        self.client = client
        self.current_player = player1
        self.player1 = player1
        self.player2 = player2
        self.player1_moves = []
        self.player2_moves = []
        self.board = [['' for _ in range(3)] for _ in range(3)]
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != '':
                return row[0]
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != '':
                return self.board[0][col]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != '':
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != '':
            return self.board[0][2]
        return None

    def is_full(self):
        return all(self.board[y][x] != '' for x in range(3) for y in range(3))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.player1 or interaction.user == self.player2
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        winner = self.player1 if self.player1 != self.current_player else self.player2
        await self.interaction.edit_original_response(content=f'{self.current_player.mention} left the game. {winner.mention} wins!', view=self)
        self.client.curr_players.pop(self.interaction.message.id, None)


class Games(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.curr_players = {}

    play_group = Group(name='play', description='Games group')

    @play_group.command(name='ttt', description='Tic Tac Toe')
    @app_commands.checks.has_any_role(750117211087044679, 775950201940606976, 809471606787145767)
    async def ttt(self, interaction: discord.Interaction, user: discord.Member):
        if interaction.user.id in self.client.curr_players:
            return await interaction.response.send_message(f"You're already in a game!", ephemeral=True)
        if user.id in self.client.curr_players:
            return await interaction.response.send_message(f"They're already in a game!", ephemeral=True)
        
        msg = await interaction.response.send_message(f"{user.mention}, {interaction.user.mention} is challenging you to a tic-tac-toe game.", view=ConfirmButton(client=self.client, author=interaction.user, opponent=user, interaction=interaction))
        self.client.curr_players[msg.id] = [interaction.user.id]


async def setup(client):
    await client.add_cog(Games(client))
