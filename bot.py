
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, InlineQueryHandler, CallbackContext, CallbackQueryHandler
from datetime import datetime, timedelta
from dotenv import load_dotenv

import os.path

from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests
import itertools
from random import shuffle, random, choice
import pytz
import json

max_int = 2147483647



load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

token = os.getenv('token')

creds = service_account.Credentials.from_service_account_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)

# Set up the Sheets API client
service = build('sheets', 'v4', credentials=creds)

# Define the spreadsheet ID and range of cells to read
spreadsheet_id = os.getenv('sheet_id')
range_name = "'Infoo ja osallistujat'!C66:Q86"
bed_range = "'Infoo ja osallistujat'!C110:G131"
score_range = "'Infoo ja osallistujat'!AN28:AT51"


# Define the time zone
finnish_tz = pytz.timezone('Europe/Helsinki')

# Define the signup, payment, mokki start, and mokki end times in Finnish time
signup_time = finnish_tz.localize(datetime(2025, 5, 10, 13, 37, 0))
signup_end = finnish_tz.localize(datetime(2025, 7, 9, 3, 0, 0))
payment_time = finnish_tz.localize(datetime(2025, 6, 30, 13, 37, 10))
mokki_time = finnish_tz.localize(datetime(2025, 7, 4, 16, 0, 0))
mokki_end = finnish_tz.localize(datetime(2025, 7, 6, 12, 0, 0))
season_start = finnish_tz.localize(datetime(2025, 4, 19, 0, 0, 0))

weather_friday_time = finnish_tz.localize(datetime(2025,  7, 4, 12, 0, 0))
weather_saturday_time = finnish_tz.localize(datetime(2025, 7, 5, 12, 0, 0))

weather_api = "https://api.open-meteo.com/v1/forecast?latitude=66.716602&longitude=24.683088&hourly=temperature_2m,precipitation_probability,rain,wind_speed_10m,relative_humidity_2m&forecast_days=14"
weather_api2 = "https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=64.977558&lon=27.552603"
yrno_header = {'User-Agent': 'Fb_mokki https://github.com/AFK-ry/fb_mokki'}

def signup_is_live():
    current_time = datetime.now(finnish_tz)
    target_time = signup_time
    return current_time > target_time

def signup_is_dead():
    current_time = datetime.now(finnish_tz)
    target_time = signup_end
    return current_time > target_time

def payment_is_live():
    current_time = datetime.now(finnish_tz)
    target_time = payment_time
    return current_time > target_time

def mokki_is_live():
    current_time = datetime.now(finnish_tz)
    target_time = mokki_time
    return current_time > target_time

def find_index_of_name(list_of_lists, name):
    for index, sublist in enumerate(list_of_lists):
        if sublist[0] == name:
            return index
    return -1  

def time_remaining(destination_time):
    current_time = datetime.now(finnish_tz)
    remaining_time = destination_time - current_time

    # Extract days, hours, minutes, and seconds from the remaining time
    days = remaining_time.days
    hours, remainder = divmod(remaining_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Construct the string with the remaining time
    time_string = f"{days} päivää, {hours} tuntia, {minutes} minuuttia, ja {seconds} sekunttia"
    return time_string

def find_player(players, name):
    for player in players:
        if player['name'].lower() == name.lower().strip('<>'):
            return player
    return -1  

def get_players():
    try:
        response = requests.get("https://api.afkry.fi/API/players/")
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.json()  # Return the response content parsed as JSON
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def get_games():
    try:
        response = requests.get("https://api.afkry.fi/API/games/")
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.json()  # Return the response content parsed as JSON
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def hours_since_mokki_time():
    current_time = datetime.now(finnish_tz)
    time_difference = current_time - season_start
    hours_difference = time_difference.total_seconds() / 3600
    return hours_difference

def pick_random_line(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    return choice(lines)
        
def create_fair_games(players, numb_games):

    # Generate all possible combinations of two teams
    shuffle(players)
    team_combinations = itertools.combinations(players, 3)
    ready_teams = []
    for i in range(numb_games):
        min_score_difference = 5000
        fair_teams = None
        # Find the combination with minimum score difference
        for team in team_combinations:
            team1 = team
            rest_of_players = [p for p in players if p not in team1]
            team_combinations2 = itertools.combinations(rest_of_players, 3)
            for team2 in team_combinations2:
                team1_average_score = sum(player["score"] for player in team1) / 3
                team2_average_score = sum(player["score"] for player in team2) / 3

                score_difference = abs(team1_average_score - team2_average_score)
                if score_difference < min_score_difference:
                    min_score_difference = score_difference
                    fair_teams = (team1, team2)
        team1_average_score = sum(player["score"] for player in fair_teams[0]) / 3
        team2_average_score = sum(player["score"] for player in fair_teams[1]) / 3

        score_difference = abs(team1_average_score - team2_average_score)
        ready_teams.append(fair_teams)
        players = [p for p in players if p not in fair_teams[0] and p not in fair_teams[1]]
        if len(rest_of_players) < 6:
            return ready_teams
        team_combinations = itertools.combinations(players, 3)
    return ready_teams

def create_random_games(players, numb_games):
    shuffle(players)
    result = []
    for i in range(numb_games):
        if len(players) < 6:
            break
        team1 = [players.pop(0), players.pop(0), players.pop(0)]
        team2 = [players.pop(0), players.pop(0), players.pop(0)]
        result.append((team1, team2))
    return result

def create_ready_games():
    games = list(filter(lambda game: game["state"] == 0 or game['state'] == 1, get_games()))
    result = []
    for game in games:
        players = game["players"]
        if len(players) != 6:
            continue
        shuffle(players)
        team1 = [players[0], players[1], players[2]]
        team2 = [players[3], players[4], players[5]]
        result.append((team1, team2))
    return result

def get_teams_string(games):
    result_string = ""
    for game in games:
        team1 = game[0]
        team2 = game[1]
        team1_average_score = round(sum(player["score"] for player in team1) / 3)
        team2_average_score = round(sum(player["score"] for player in team2) / 3)

        result_string += f"{team1[0]['name']}, {team1[1]['name']}, {team1[2]['name']}\n ({team1_average_score}) --vs-- ({team2_average_score})\n{team2[0]['name']}, {team2[1]['name']}, {team2[2]['name']}\n\n"
    return result_string

def is_mokki_game(game):
    mokki_start = season_start
    game_time = datetime.strptime(game["date"], "%Y-%m-%dT%H:%M:%SZ").astimezone(finnish_tz)
    return mokki_end > game_time and mokki_start < game_time and game["state"] == 3

def is_recent_game(game, hours=24):
    now = datetime.now(finnish_tz)
    try:
        seperator = now - timedelta(hours=hours)
    except OverflowError:
        return True
    game_time = datetime.strptime(game["date"], "%Y-%m-%dT%H:%M:%SZ").astimezone(finnish_tz)
    return seperator < game_time and game["state"] == 3





async def mokki_ilmo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if(signup_is_live() != True):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Ilmo ei ole auki. Palaa asiaan 10.5 klo 13:37")   
    elif(signup_is_dead() == True): 
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Ilmo on päättynyt. Ole yhteydessä järjestäjään jos vielä haluat mukaan")   
    elif(len(args) < 1):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Kerro kuka olet '/mokille <mökkeilijän nimi>'")
    elif(update.message.chat.type != 'private'):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Pistätkö yksityisviestiä")
    else:
        keyboard = [[InlineKeyboardButton("Kyllä", callback_data='auto'),
                 InlineKeyboardButton("Ei", callback_data='ei_auto')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['user_param'] = args
        await update.message.reply_text("Onko käytössäsi auto mökki kyyteihin", reply_markup=reply_markup)

async def mokki_alkaa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if mokki_is_live() is False:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Mökkiin aikaa: {time_remaining(mokki_time)}")    
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Mökkiin aikaa: Mökki on jo, miksi kyselet etkä pelaa")

async def maksettu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if(payment_is_live() != True):
        time_string = time_remaining(payment_time)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Maksu ei ole auki. Maksuun aikaa: {time_remaining(payment_time)}")
        return
    if(len(args) < 1):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Kerro kuka olet '/maksettu <mökkeilijän nimi>'")
        return
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]
    name = ' '.join(args)
    # if name not in names_only:
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text="'{}' ei ole ilmonnut mökille".format(name))
    #     return

    # sleeps = service.spreadsheets().values().get(
    #         spreadsheetId=spreadsheet_id,
    #         range=bed_range
    #     ).execute()
    # beds = sleeps.get('values', [])
    # beds = [cell for cell in beds if cell]
    # bed_names_only = [cell[0] for cell in beds if cell]
    index = find_index_of_name(names, name)
    # if name in bed_names_only:
    if name in names_only:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="'{}' on jo maksanut".format(name))
        return
    # bed_count = len(bed_names_only)
    bed_count = len(names_only)
    # beds.append([name])
    print(names)
    names.append([name, '', '', '', '', '', '', 'kyllä'])
    # request_body = {
    #     'values': beds
    # }
    request_body = {
        'values': names
    }
    # result = service.spreadsheets().values().update(
    #     spreadsheetId=spreadsheet_id,
    #     range=bed_range,
    #     valueInputOption='USER_ENTERED',
    #     body=request_body
    # ).execute()
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=request_body
    ).execute()
    # if(index > -1):
        # names[index][7] = 'kyllä'
        # request_body = {
        #     'values': names
        # }
        # result = service.spreadsheets().values().update(
        #     spreadsheetId=spreadsheet_id,
        #     range=range_name,
        #     valueInputOption='USER_ENTERED',
        #     body=request_body
        # ).execute()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Kiitos maksusta. {} nukkuu sijalla {}".format(name, bed_count + 1))

def get_sijoituket():
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=score_range
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]
    players = get_players()
    result = []
    for index, name in enumerate(names_only):
        player = find_player(players, name)
        original = 0
        try:
            if index < len(names) and len(names[index]) > 5:
                original = int(names[index][5])
        except ValueError:
            pass
        if player == -1:
            result.append({'name': name, 'score': 'ei löytynyt', 'change': original * - 1})
        else:
            player['change'] = player['score'] - original
            result.append(player)
    return sorted(result, key=lambda x: x['change'], reverse=True)

async def sijoitukset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = get_sijoituket()
    return_text = ''
    for index, player in enumerate(result):
        return_text += '{}. {} - {} ({})\n'.format(index + 1, player['name'], player['score'], player['change'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=return_text)

async def create_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    numb_teams = 3
    # if mokki_is_live() is False:
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Ei tehdä tiimejä ennen mökkiä")
    #     return    
    if len(args) > 0:
        try:
            if(args[0] == "ready"):
                pass
            else:
                numb_teams = int(args[0])
                if numb_teams < 1 or numb_teams > 3:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text="Ensimmäisen argumentin pitää olla numero 1|2|3 tai 'ready'")
                    return    
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Ensimmäisen argumentin pitää olla numero 1|2|3 tai 'ready'")
            return
    if len(args) == 2 and args[1] != "rand":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="toinen argumentti voi olla 'rand' randomeille tiimeille")
        return
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=score_range
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]
    if len(names_only) < numb_teams * 6:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Liian vähän pelaajia {len(names_only)}/{numb_teams * 6} tiimin tekemiseen")
        return
    players = get_players()
    result = []
    for index, name in enumerate(names_only):
        player = find_player(players, name)
        original = 0
        try:
            original = int(names[index][5])
        except ValueError:
            pass
        if player == -1:
            result.append({'name': name, 'score': 0})
        else:
            result.append(player)
    if len(args) == 2 and args[1] == "rand":
        games = create_random_games(result, numb_teams)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_teams_string(games))
    elif len(args) == 1 and args[0] == "ready":
        games = create_ready_games()
        if len(games) == 0:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Ei valmiita pelejä")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=get_teams_string(games))
    else:
        games = create_fair_games(result, numb_teams)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_teams_string(games))
    # await context.bot.send_message(chat_id=update.effective_chat.id, text=return_text)

async def kaljaa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=score_range
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]
    players = get_sijoituket()
    games = get_games()
    result = []
    mokki_players = []
    for index, name in enumerate(names_only):
        player = find_player(players, name)
        if player == -1:
            mokki_players.append({'name': name, 'score': 'ei löytynyt', 'kaljaa': 0})
        else:
            player["kaljaa"] = 0
            player["score"] = player["score"]
            mokki_players.append(player)
    for game in games:
        if(is_mokki_game(game)):
            for player in game["players"]:
                found_player = list(filter(lambda mokkilainen: mokkilainen["name"] == player["name"], mokki_players))
                if len(found_player) > 0:
                    found_player[0]["kaljaa"] += 2.66666 * ( game["team1_score"] + game["team2_score"] )
    mokki_players = sorted(mokki_players, key=lambda x: x['kaljaa'], reverse=True)
    total_beer = sum(player['kaljaa'] for player in mokki_players)
    return_text = 'Nimi - Kaljoja | Elo per kalja\n'
    for index, player in enumerate(mokki_players):
        try:
            elo_beer = round(player["change"] / player["kaljaa"], 2)
        except:
            elo_beer = "NaN"
        return_text += '{}. {} - {} | {}\n'.format(index + 1, player['name'], round(player['kaljaa'], 2), elo_beer)
    hours = hours_since_mokki_time()
    return_text += f"\nKaljaa yhteensä: {round(total_beer + 0.009, 2)}"
    return_text += f"\nKaljaa euroissa (1.27 kpl): {round((total_beer + 0.009)*1.27, 2)}€"
    return_text += f"\nKaljaa per tunti: {round(total_beer / hours, 2)}"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=return_text)

async def peleja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=score_range
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]

    message = update.message.text.split(" ", 1)

    if(len(message) == 2):
        try:
            hours = int(message[1])
        except:
            hours = 24
    else:
        hours = 24

    players = get_players()
    games = get_games()
    games = list(filter(lambda game: is_recent_game(game, hours), games))
    result = []
    mokki_players = []
    for index, name in enumerate(names_only):
        player = find_player(players, name)
        if player == -1:
            mokki_players.append({'name': name, 'games': 0})
        else:
            player["games"] = 0
            mokki_players.append(player)
    for game in games:
        for player in game["players"]:
            found_player = list(filter(lambda mokkilainen: mokkilainen["name"] == player["name"], mokki_players))
            if len(found_player) > 0:
                found_player[0]["games"] += 1
    mokki_players = sorted(mokki_players, key=lambda x: x['games'], reverse=True)    
    return_text = 'Nimi - pelatut pelit {}h aikana\n'.format(hours)
    for index, player in enumerate(mokki_players):
        return_text += '{}. {} - {}\n'.format(index + 1, player['name'], player['games'])

    await context.bot.send_message(chat_id=update.effective_chat.id, text=return_text)
            
async def kys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if random() < 0.01:
        files = ['mattoteline.txt']
        line = pick_random_line(choice(files))
        await context.bot.send_message(chat_id=update.effective_chat.id, text=line)
    else:
        try:
            response = requests.get("https://v2.jokeapi.dev/joke/Dark?blacklistFlags=racist")
            joke = response.json()
            joke_string = ""
            if joke["type"] == "single":
                joke_string = joke["joke"]
            elif joke["type"] == "twopart":
                joke_string = joke["setup"] + "\n\n" + joke["delivery"]
            else:
                joke_string = "Jotain meni vikaan"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=joke_string)
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Kyssäsin")


async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_param = context.user_data.get('user_param')
    name = ' '.join(user_param)
    if query.data == 'auto' or query.data == 'ei_auto':
        keyboard = [[InlineKeyboardButton("Kyllä", callback_data='torstai'),
                 InlineKeyboardButton("En", callback_data='ei_torstai')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['user_param'] = user_param
        context.user_data['auto'] = 'kyllä' if query.data == 'auto' else 'ei'
        await query.edit_message_text(text="Lähdetkö mökille jo torstaina jos lähtijöitä on yli pelillinen", reply_markup=reply_markup)
    elif query.data == 'torstai' or query.data == 'ei_torstai':
        keyboard = [[InlineKeyboardButton("Kyllä", callback_data='kylla'),
                 InlineKeyboardButton("Ei", callback_data='ei')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['user_param'] = user_param
        context.user_data['torstai'] = 'x' if query.data == 'torstai' else ''
        await query.edit_message_text(text="Haluatko varmasti lähteä mökille? Ilmoittautuminen on sitovaa", reply_markup=reply_markup)
    elif query.data == 'kylla':
        # Make a request to read the data from the spreadsheet
        signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        names = signups.get('values', [])
        cells = len(names)
        names = [cell for cell in names if cell]
        for i in names:
            if len(i) < 15:
                i = i + [''] * (15 - len(i))
        names_only = [cell[0] for cell in names if cell]
        if name not in names_only:
            auto = context.user_data.get('auto')
            torstai = context.user_data.get('torstai')
            names.append([name, '', '', '', '', auto, '', 'ei', '', '', '', '', '', '', torstai])
        else:
            reply = name + ' on jo mokillä'
            await query.edit_message_text(text=reply)
            return
        for i in range(cells - len(names)):
            names.append(['', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        request_body = {
            'values': names
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=request_body
        ).execute()
        response = 'Olet ilmoittautunut mökille ' + name
        await query.edit_message_text(text=response)
    elif query.data == 'ei':
        await query.edit_message_text(text="Ei sitten, ehkä ens kerralla")


async def laturi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signups = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=score_range
        ).execute()
    names = signups.get('values', [])
    names = [cell for cell in names if cell]
    names_only = [cell[0] for cell in names if cell]
    name1 = choice(names_only)
    name2 = choice(list(filter(lambda x: x != name1, names_only)))
    phrases = [f"Laturin hakee {name1}.", f"Viititkö {name1} hakea laturin?", f"Haekko {name1} laturin?", f"Käy {name1} hakee laturi."]
    places = ["mökkiin", "vessaan", "volvoon", "huoneeseensa", "Ouluun", "parisänkyyn", "johonkin", "laturimökkiin", "yöpöydälle", "reppuun", "saunaan", "järveen", "pakuun"]
    devices = ["oneplussan", "iphonen", "huawein", "jbl:n", "teslan", "samsungin", "läppärin"]
    colors = ["punanen", "sininen", "musta", "valkonen", "pinkki", "hajonnut", "harmaa", "huono", "lyhyt", "pitkä", "vanha"]

    if random() < 0.2:
        current_time = datetime.now(finnish_tz)
        hours = current_time.hour
        name1 = names_only[(hours*7)%len(names_only)]
        name2 = names_only[(hours*7+1)%len(names_only)]
        name3 = names_only[(hours*7+2)%len(names_only)]
        phrase = f"Nyt on paha tilanne!!! {name1} sun on pakko hakia laturi!!"
        place = f" {name2} ja {name3} käytti sitä viimeksi ja ne vei sen äsken mukanaan {places[(hours*7)%len(places)]}!!"
        type = f" Niillä pitäs olla ainakin {colors[(hours*7)%len(colors)]} {devices[(hours*7)%len(devices)]} laturi mutta ota kaikki mitä löydät!"
    else:
        place = ''
        if random() < 0.5:
            place = f" {name2} jätti sen {choice(places)}."
        type = ''
        if random() < 0.5:
            type = f" Semmonen {choice(colors)} {choice(devices)} laturi."
        phrase = choice(phrases)

    response = f"{phrase}{place}{type}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

def get_weather_data(data):
    details = data["data"]["instant"]["details"]
    six_hours = data["data"]["next_6_hours"]["details"]
    return f"Lämpötila: {details['air_temperature']}°C\nTuuli: {details['wind_speed']}m/s\nKosteus: {details['relative_humidity']}%\nSateen todennäköisyys: {six_hours['probability_of_precipitation']}%\nSade: {six_hours['precipitation_amount']}mm"

async def saa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get(weather_api2, headers=yrno_header)
    weather_data = response.json()
    result = "Pekkalantie 4B\n\n"
    current_time = datetime.now(finnish_tz)
    thursday = 0
    friday = 0
    saturday = 0
    for index, data in enumerate(weather_data["properties"]["timeseries"]):
        given_time = datetime.strptime(data["time"], "%Y-%m-%dT%H:%M:%SZ").astimezone(finnish_tz)
        # if given_time >= mokki_time and thursday == 0:
        #     result += f"{given_time.strftime('%d.%m.%Y klo %H:%M')}\n"
        #     result += f"{get_weather_data(data)}\n\n"
        #     thursday = 1
        if given_time >= weather_friday_time and friday == 0:
            result += f"{given_time.strftime('%d.%m.%Y klo %H:%M')}\n"
            result += f"{get_weather_data(data)}\n\n"
            friday = 1
        if given_time >= weather_saturday_time and saturday == 0:
            result += f"{given_time.strftime('%d.%m.%Y klo %H:%M')}\n"
            result += f"{get_weather_data(data)}\n\n"
            saturday = 1
        if given_time > mokki_time and given_time > current_time and result == "Pekkalantie 4B\n\n":
            result += f"{given_time.strftime('%d.%m.%Y klo %H:%M')}\n"
            result += f"{get_weather_data(data)}\n\n"
        # if given_time == mokki_time or given_time == weather_friday_time or given_time == weather_saturday_time or (given_time > mokki_time and given_time > current_time and result == "Raanutie 7\n\n"):
        #     result += f"{given_time.strftime('%d.%m.%Y klo %H:%M')}\n"
        #     result += f"{get_weather_data(data)}\n\n"
    if result != "Pekkalantie 4B\n\n":
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Säätietoja ei löytynyt")

        
if __name__ == '__main__':
    application = ApplicationBuilder().token(token).build()
    
    mokki_handler = CommandHandler('mokille', mokki_ilmo)
    mokki_reply_handler = CallbackQueryHandler(button)
    maksu_handler = CommandHandler('maksettu', maksettu)
    sijoitukset_handler = CommandHandler('sijoitukset', sijoitukset)
    aika_handler = CommandHandler('mokki', mokki_alkaa)
    tiimi_handler = CommandHandler('tiimit', create_teams)
    kys_handler = CommandHandler('kys', kys)
    kalja_handler = CommandHandler('kaljaa', kaljaa)
    peleja_handler = CommandHandler('peleja', peleja)
    laturi_handler = CommandHandler('laturi', laturi)
    saa_handler = CommandHandler('saa', saa)

    application.add_handler(mokki_handler)
    application.add_handler(mokki_reply_handler)
    application.add_handler(maksu_handler)
    application.add_handler(sijoitukset_handler)
    application.add_handler(aika_handler)
    application.add_handler(tiimi_handler)
    application.add_handler(kys_handler)
    application.add_handler(kalja_handler)
    application.add_handler(peleja_handler)
    application.add_handler(laturi_handler)
    application.add_handler(saa_handler)

    
    application.run_polling()


# mokille - ilmoittautuminen mökille
# maksettu - ilmoita että ole maksanut mökin
# sijoitukset - lista score muutoksista mökin aikana
# mokki - koska mökki on
# tiimit - /tiimit <pelien määrä> <rand>
# kys - ???
# kaljaa - Mökillä juodut kaljat
# peleja -  Pelejä viimeisen x tunnin aikana
# laturi - Kuka hakee laturin
# saa - Säätiedot mökille
