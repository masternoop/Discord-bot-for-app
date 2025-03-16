import discord
import mysql.connector
import requests
from discord.ext import commands, tasks
import random
import datetime


last_processed_timestamp = datetime.datetime.utcnow()

gangid = 25546
shedid = 1349
leaderid = 673769777898061825              #idc if you see this stuff
channel_id = 989186559536431184

# database connection
def connect_to_db():
    return mysql.connector.connect(
        host="localhost",
        user="botuser",
        password="Nope",
        database="olympus_bot"
    )


db = connect_to_db()
cursor = db.cursor()

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True  # Enable member intent

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def get_api_data(endpoint):
    url = f"https://stats.olympus-entertainment.com/api/v3.0{endpoint}"  
    headers = {"Authorization": f"Token Nice Try"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            print("Error: Received invalid JSON from the API.")
            return None
    else:
        print("Error: API request failed.")
        return None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

def requires_linked_steam():
    async def predicate(ctx):
        global db, cursor
        user_id = ctx.author.id
        try:
            cursor.execute("SELECT steam_id FROM user_links WHERE discord_id = %s", (user_id,))
        except mysql.connector.errors.OperationalError:
            db = connect_to_db()
            cursor = db.cursor()
            cursor.execute("SELECT steam_id FROM user_links WHERE discord_id = %s", (user_id,))
        
        result = cursor.fetchone()
        
        if not result:
            await ctx.send("You must link your Discord to your Steam ID first using `!link <steamid>`.")
            return False
        return True
    
    return commands.check(predicate)

# !stats
@bot.command()
@requires_linked_steam()
async def stats(ctx):
    data = get_api_data(f"/gangs/25546/")
    if data:
        embed = discord.Embed(title=f"{data['name']} Stats", color=0x00ff00)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=False)
        embed.add_field(name="Kills", value=data['kills'], inline=True)
        embed.add_field(name="Deaths", value=data['deaths'], inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Error fetching gang stats.")

# !caps
@bot.command()
@requires_linked_steam()
async def caps(ctx):
    cartels = get_api_data("/cartels/")
    if cartels:
        embed = discord.Embed(title="Cartel Capture Status", color=0x00ff00)
        for cartel in cartels:
            embed.add_field(name=cartel['full_name'], value=f"Captured by: {cartel['gang_name']} ({cartel['progress']}%)", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Error fetching cartel status.")

# !player
@bot.command()
@requires_linked_steam()
async def player(ctx, member: discord.Member = None):
    
    
    
    member = member or ctx.author
    user_id = member.id

    
    cursor.execute("SELECT steam_id FROM user_links WHERE discord_id = %s", (user_id,))
    result = cursor.fetchone()

    if not result:
        await ctx.send(f"{member.mention}, you have not linked your Steam ID. Use `!link <steamid>` first.")
        return

    steam_id = result[0]  

    
    player_data = get_api_data(f"/players/{steam_id}/")

    if not player_data or "stats" not in player_data:
        await ctx.send(f"Error: Could not fetch stats for `{member.display_name}` (Steam ID: `{steam_id}`).")
        return

    stats = player_data["stats"]

    
    playtime_minutes = sum([
        stats.get("playtime_civ", 0),
        stats.get("playtime_cop", 0),
        stats.get("playtime_med", 0),
        stats.get("playtime_swat", 0)
    ])
    playtime_hours = round(playtime_minutes / 60, 2)

    kills = stats.get("kills", "N/A")
    deaths = stats.get("deaths", "N/A")
    bank = player_data.get("bank", "N/A")

    
    embed = discord.Embed(title=f"Player Stats: {member.display_name}", color=0x3498db)
    embed.add_field(name="Steam ID", value=steam_id, inline=False)
    embed.add_field(name="Total Playtime", value=f"{playtime_hours} hours", inline=False)
    embed.add_field(name="Kills", value=kills, inline=False)
    embed.add_field(name="Deaths", value=deaths, inline=False)
    embed.add_field(name="Bank", value=bank, inline=False)

    await ctx.send(embed=embed)

# Cartel Session
@bot.command()
@requires_linked_steam()
async def start(ctx):
    
    cursor.execute("SELECT id FROM cartel_sessions WHERE end_time IS NULL LIMIT 1")
    existing_session = cursor.fetchone()

    if existing_session:
        await ctx.send("A cartel session is already active! End the current session before starting a new one.")
        return

   
    gang_data = get_api_data("/gangs/25546")
    if not gang_data:
        await ctx.send("Error fetching gang data. Try again later.")
        return

    start_balance = gang_data['bank']
    
    
    cursor.execute("INSERT INTO cartel_sessions (total_earnings, start_balance) VALUES (0, %s)", (start_balance,))
    db.commit()

    cursor.execute("SELECT LAST_INSERT_ID()")
    session_id = cursor.fetchone()[0]

    embed = discord.Embed(title="Cartel Session Started", description="Click the button below to join.", color=0x00ff00)

    class JoinButton(discord.ui.View):
        def __init__(self, session_id):
            super().__init__()
            self.session_id = session_id

        @discord.ui.button(label="Join Session", style=discord.ButtonStyle.green)
        async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = interaction.user.id
            username = interaction.user.name

            
            cursor.execute("SELECT COUNT(*) FROM cartel_participants WHERE session_id = %s AND user_id = %s", 
                        (self.session_id, user_id))
            already_joined = cursor.fetchone()[0]

            if already_joined > 0:
                await interaction.response.send_message("You have already joined this cartel session!", ephemeral=True)
                return

            
            cursor.execute("INSERT INTO cartel_participants (session_id, user_id, username) VALUES (%s, %s, %s)",
                        (self.session_id, user_id, username))
            db.commit()

            await interaction.response.send_message(f"{username} joined the cartel session!", ephemeral=True)


    view = JoinButton(session_id)
    await ctx.send(embed=embed, view=view)


tax_player_id = 401182546739724288  

# !end
@bot.command()
@requires_linked_steam()
async def end(ctx):
    
    cursor.execute("SELECT id, start_balance FROM cartel_sessions WHERE end_time IS NULL LIMIT 1")
    session = cursor.fetchone()

    if not session:
        await ctx.send("No active cartel session found. Start a new session with `!start`.")
        return

    session_id, start_balance = session

    
    gang_data = get_api_data("/gangs/25546")
    if not gang_data:
        await ctx.send("Error fetching gang data. Try again later.")
        return

    end_balance = gang_data['bank']
    earnings = max(0, end_balance - start_balance)

    # Calculate tax
    logan_amount = earnings * 0.085
    logantax = earnings - logan_amount
    tax_amount = logantax * .05
    earnings_after_tax = logantax - tax_amount

    
    cursor.execute("INSERT INTO player_money (user_id, balance) VALUES (%s, %s) "
                   "ON DUPLICATE KEY UPDATE balance = balance + %s",
                   (tax_player_id, logan_amount, logan_amount))
    db.commit()

    cursor.execute("UPDATE cartel_sessions SET end_time = NOW(), total_earnings = %s WHERE id = %s", (earnings_after_tax, session_id))
    db.commit()

    cursor.execute("SELECT user_id, username FROM cartel_participants WHERE session_id = %s", (session_id,))
    participants = cursor.fetchall()

    if not participants:
        await ctx.send("No participants joined this session.")
        return

    num_players = len(participants)
    share = earnings_after_tax // num_players if num_players > 0 else 0

    embed = discord.Embed(title="Cartel Session Ended", color=0xff0000)
    embed.add_field(name="Total Earnings", value=f"${earnings_after_tax:,}", inline=False)

    for user_id, username in participants:
        cursor.execute("INSERT INTO player_money (user_id, username, balance) VALUES (%s, %s, %s) "
                       "ON DUPLICATE KEY UPDATE balance = balance + %s",
                       (user_id, username, share, share))
        db.commit()
        embed.add_field(name=username, value=f"Receives: ${share:,}", inline=False)

    await ctx.send(embed=embed)

# !players
@bot.command()
@requires_linked_steam()
async def players(ctx):
    servers = get_api_data("/servers/")
    if servers:
        total = sum(server['total'] for server in servers)
        await ctx.send(f"Total Olympus Players: {total}")
    else:
        await ctx.send("Error fetching player count.")

# !money +
# !money -
@bot.command()
@requires_linked_steam()
async def money(ctx, action: str, member: discord.Member, amount: int):
    """Adds or subtracts money owed to a user using Discord mentions. Only available for users with gang rank 4 or higher."""
    
    user_id = ctx.author.id  

    
    cursor.execute("SELECT steam_id FROM user_links WHERE discord_id = %s", (user_id,))
    result = cursor.fetchone()

    if not result:
        await ctx.send("You must link your Steam ID first using `!link <steamid>`.")
        return

    steam_id = result[0]

    
    user_data = get_api_data(f"/players/{steam_id}/")

    
    if not user_data or "gang" not in user_data:
        await ctx.send("You do not have the required gang rank to use this command.")
        return

    gang_rank = user_data["gang"].get("rank", 0)

    if gang_rank < 4:
        await ctx.send("You must be rank 4 or higher in the gang to use this command.")
        return

    
    target_id = member.id
    target_name = member.name

    
    cursor.execute("SELECT user_id, balance FROM player_money WHERE user_id = %s", (target_id,))
    result = cursor.fetchone()

    if result:
        db_user_id, current_balance = result
    else:
        
        cursor.execute("INSERT INTO player_money (user_id, username, balance) VALUES (%s, %s, %s)", 
                       (target_id, target_name, 0))
        db.commit()

        cursor.execute("SELECT user_id, balance FROM player_money WHERE user_id = %s", (target_id,))
        result = cursor.fetchone()
        db_user_id, current_balance = result  

   
    if action == "+":
        new_balance = current_balance + amount
    elif action == "-":
        new_balance = max(0, current_balance - amount)  
    else:
        await ctx.send("Invalid action! Use `+` to add or `-` to subtract money.")
        return

    
    cursor.execute("UPDATE player_money SET balance = %s WHERE user_id = %s", (new_balance, db_user_id))
    db.commit()

    await ctx.send(f"Updated balance for {member.mention}: **${new_balance:,}**")

# !balance 
@bot.command()
@requires_linked_steam()
async def balance(ctx, member: discord.Member = None):
    """Checks a player's balance using Discord mentions. Defaults to the command user if no player is mentioned."""

    
    member = member or ctx.author
    user_id = member.id

    
    cursor.execute("SELECT balance FROM player_money WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()

    if not result:
        await ctx.send(f"{member.mention} has no recorded balance.")
        return

    balance = result[0]
    await ctx.send(f"{member.mention} has a balance of **${balance:,}**")

@bot.command()
@requires_linked_steam()
async def split(ctx, *, input_data: str):
    try:
        
        players_part = input_data.split(" ")

        if not players_part:
            await ctx.send("You must mention at least one player to split the loot.")
            return

        embed = discord.Embed(title="Loot Choice Order", color=0x00ff00)

  
        members = [await commands.MemberConverter().convert(ctx, player) for player in players_part]

        
        random.shuffle(members)

        
        for index, member in enumerate(members, start=1):
            embed.add_field(name=f"Pick {index}", value=member.display_name, inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"Error processing the command: {e}")

@bot.command()
async def link(ctx, steam_id: str):
    
    
    
    if not steam_id.isdigit() or len(steam_id) < 15 or len(steam_id) > 20:
        await ctx.send("Invalid Steam ID. Please enter a valid 15-20 digit Steam ID.")
        return
    
    user_id = ctx.author.id
    username = ctx.author.name

    
    cursor.execute("SELECT steam_id FROM user_links WHERE discord_id = %s", (user_id,))
    existing_link = cursor.fetchone()

    if existing_link:
        await ctx.send(f"Your account is already linked to Steam ID `{existing_link[0]}`.")
        return

    cursor.execute("INSERT INTO user_links (discord_id, username, steam_id) VALUES (%s, %s, %s)", 
                   (user_id, username, steam_id))
    db.commit()

    await ctx.send(f"Successfully linked your Discord to Steam ID `{steam_id}`!")

@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(title="Bot Commands", description="Here are the available commands and how to use them:", color=0x3498db)

    embed.add_field(name="🔗 !link <steamid>", value="Links your Discord account to your Steam ID. Required to use bot commands.", inline=False)
    embed.add_field(name="📊 !stats", value="View gang stats.", inline=False)
    embed.add_field(name="📢 !caps", value="View who controls the cartels and their percentages.", inline=False)
    embed.add_field(name="👤 !player <@DISCORDNAME>", value="View a player's stats.", inline=False)
    embed.add_field(name="🏆 !start", value="Start a cartel session. Players can join using a button.", inline=False)
    embed.add_field(name="💰 !end", value="End the cartel session and divide up the earnings automatically.", inline=False)
    embed.add_field(name="📌 !players", value="Check the total number of players currently online.", inline=False)
    embed.add_field(name="💵 !money + <@DISCORDNAME> <amount>", value="(Requires R4 in game) Add money owed to a player.", inline=False)
    embed.add_field(name="💸 !money - <@DISCORDNAME> <amount>", value="(Requires R4 in game) Remove money owed from a player.", inline=False)
    embed.add_field(name="📊 !balance <@DISCORDNAME>", value="Check a player's balance. Defaults to the command user if no player is mentioned.", inline=False)
    embed.add_field(name="🔀 !split <players>", value="Randomly decides choice order.", inline=False)
    
    embed.set_footer(text="Use these commands in the server to interact with the bot!")

    await ctx.send(embed=embed)

bot.run("no thanks")
