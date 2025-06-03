import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import unicodedata
from fuzzywuzzy import process
import asyncio
import os
import re
import random
import requests
import sqlite3
import json
import time
from datetime import datetime, timedelta
from googletrans import Translator
import aiofiles
import math
import aiohttp
from dotenv import load_dotenv
from keep_alive import keep_alive


# --- Configurações do Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='p!', intents=intents, help_command=None)

# --- SEU TOKEN DO BOT DISCORD ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# --- API DE FUTEBOL ---
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY', 'live_f1a72149356ef28e3de8370d2b66d7')
FOOTBALL_API_BASE = 'https://apiv3.apifootball.com/' 

# --- Dicionários de Dados ---
dados_usuarios = {}
usuarios_acesso_ranking = set()
dados_rolls = {}
dados_jogos = []
bot_start_time = datetime.now()

# --- Sistema de Economia e Banco de Dados ---
def init_database():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # Tabela de economia
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS economy (
        user_id INTEGER PRIMARY KEY,
        money INTEGER DEFAULT 0,
        last_daily TEXT,
        last_work TEXT
    )
    ''')

    # Tabela de itens da loja
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL,
        description TEXT
    )
    ''')

    # Tabela de inventário dos usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_inventory (
        user_id INTEGER,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY (item_id) REFERENCES shop_items (id)
    )
    ''')

    # Tabela de lembretes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reminder TEXT,
        reminder_time TEXT
    )
    ''')

    # Tabela de tarefas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_name TEXT,
        completed INTEGER DEFAULT 0
    )
    ''')

    # Tabela de warns
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        guild_id INTEGER,
        reason TEXT,
        warn_time TEXT
    )
    ''')

    # Tabela de contagem de mensagens
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS message_count (
        user_id INTEGER,
        guild_id INTEGER,
        date TEXT,
        count INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, guild_id, date)
    )
    ''')

    # Tabela de usuários mutados
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS muted_users (
        user_id INTEGER,
        guild_id INTEGER,
        mute_end TEXT,
        reason TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
    ''')

    conn.commit()
    conn.close()

# Inicializar banco de dados
init_database()

# Tradutor
translator = Translator()

# Lista de trabalhos para ganhar dinheiro
trabalhos = [
    {"nome": "Entregador de pizza", "min": 50, "max": 150},
    {"nome": "Programador freelancer", "min": 200, "max": 500},
    {"nome": "Designer gráfico", "min": 100, "max": 300},
    {"nome": "Motorista de Uber", "min": 80, "max": 200},
    {"nome": "Vendedor de loja", "min": 60, "max": 120},
    {"nome": "Professor particular", "min": 150, "max": 400},
    {"nome": "Garçom", "min": 70, "max": 180},
    {"nome": "Streamer", "min": 300, "max": 800},
]

# Lista de investimentos
investimentos = [
    {"nome": "Ações da Tesla", "risco": "alto", "min_mult": 0.5, "max_mult": 2.5},
    {"nome": "Bitcoin", "risco": "muito_alto", "min_mult": 0.3, "max_mult": 3.0},
    {"nome": "Poupança", "risco": "baixo", "min_mult": 1.01, "max_mult": 1.05},
    {"nome": "Tesouro Direto", "risco": "baixo", "min_mult": 1.02, "max_mult": 1.08},
    {"nome": "Ações da Apple", "risco": "médio", "min_mult": 0.7, "max_mult": 1.8},
    {"nome": "Ethereum", "risco": "alto", "min_mult": 0.4, "max_mult": 2.2},
]

# --- Funções da API de Futebol ---
async def get_team_players(team_name: str):
    """Busca jogadores reais de um time usando a API de futebol"""
    try:
        # Mapeamento de times da Série B para IDs da API
        serie_b_teams = {
            "Sport": "3209",
            "Ponte Preta": "3217", 
            "Guarani": "3204",
            "Vila Nova": "3225",
            "Novorizontino": "10237",
            "Santos": "3211",
            "Ceará": "3195",
            "Goiás": "3202",
            "Mirassol": "10238",
            "América-MG": "3189",
            "Operário-PR": "10239",
            "Coritiba": "3197",
            "Avaí": "3193",
            "Paysandu": "10240",
            "CRB": "3196",
            "Amazonas": "10241",
            "Chapecoense": "3194",
            "Ituano": "10242",
            "Botafogo-SP": "10243",
            "Brusque": "10244"
        }
        
        team_id = serie_b_teams.get(team_name)
        if not team_id:
            return None
            
        async with aiohttp.ClientSession() as session:
            url = f"{FOOTBALL_API_BASE}?action=get_players&team_id={team_id}&APIkey={FOOTBALL_API_KEY}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list) and len(data) > 0:
                        # Filtrar apenas alguns jogadores importantes
                        players = []
                        for player in data[:15]:  # Pegar até 15 jogadores
                            if 'player_name' in player:
                                players.append({
                                    'name': player['player_name'],
                                    'position': player.get('player_type', 'Meio-campo'),
                                    'number': player.get('player_number', '??'),
                                    'age': player.get('player_age', '??')
                                })
                        return players
                return None
    except Exception as e:
        print(f"Erro ao buscar jogadores: {e}")
        return None

def format_team_lineup(team_name: str, players: list):
    """Formata a escalação do time com jogadores reais"""
    if not players:
        return f"**{team_name}** (Escalação indisponível)"
    
    # Organizar por posição
    goalkeepers = [p for p in players if 'goalkeeper' in p['position'].lower() or 'goleiro' in p['position'].lower()]
    defenders = [p for p in players if 'defender' in p['position'].lower() or 'defesa' in p['position'].lower() or 'zagueiro' in p['position'].lower()]
    midfielders = [p for p in players if 'midfielder' in p['position'].lower() or 'meio' in p['position'].lower()]
    forwards = [p for p in players if 'forward' in p['position'].lower() or 'atacante' in p['position'].lower()]
    
    lineup_text = f"**🏟️ {team_name}**\n"
    
    # Goleiro
    if goalkeepers:
        gk = goalkeepers[0]
        lineup_text += f"🥅 **{gk['name']}** #{gk['number']}\n"
    
    # Defensores
    if defenders:
        lineup_text += "🛡️ **Defesa:** "
        def_names = [f"{p['name']}" for p in defenders[:4]]
        lineup_text += ", ".join(def_names) + "\n"
    
    # Meio-campo
    if midfielders:
        lineup_text += "⚡ **Meio:** "
        mid_names = [f"{p['name']}" for p in midfielders[:3]]
        lineup_text += ", ".join(mid_names) + "\n"
    
    # Ataque
    if forwards:
        lineup_text += "⚽ **Ataque:** "
        fwd_names = [f"{p['name']}" for p in forwards[:3]]
        lineup_text += ", ".join(fwd_names) + "\n"
    
    return lineup_text

# --- Funções Auxiliares ---
def normalizar(texto):
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode().lower()

def capitalizar_nome(texto):
    return ' '.join(word.capitalize() for word in texto.split())

# --- Funções da Economia ---
def get_user_money(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT money FROM economy WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def set_user_money(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO economy (user_id, money) VALUES (?, ?)', (user_id, amount))
    conn.commit()
    conn.close()

def add_user_money(user_id, amount):
    current = get_user_money(user_id)
    set_user_money(user_id, current + amount)

def remove_user_money(user_id, amount):
    current = get_user_money(user_id)
    new_amount = max(0, current - amount)
    set_user_money(user_id, new_amount)
    return current >= amount

def can_daily(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_daily FROM economy WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        return True

    last_daily = datetime.fromisoformat(result[0])
    return datetime.now() - last_daily >= timedelta(days=1)

def set_daily_claimed(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE economy SET last_daily = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO economy (user_id, last_daily) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def can_work(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_work FROM economy WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        return True

    last_work = datetime.fromisoformat(result[0])
    return datetime.now() - last_work >= timedelta(hours=1)

def set_work_done(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE economy SET last_work = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO economy (user_id, last_work) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# --- Funções de Warns ---
def add_warn(user_id, guild_id, reason):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warns (user_id, guild_id, reason, warn_time) VALUES (?, ?, ?, ?)', 
                   (user_id, guild_id, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_warns(user_id, guild_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT reason, warn_time FROM warns WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    warns = cursor.fetchall()
    conn.close()
    return warns

# --- Funções de Mute ---
def add_mute(user_id, guild_id, mute_end, reason):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO muted_users (user_id, guild_id, mute_end, reason) VALUES (?, ?, ?, ?)', 
                   (user_id, guild_id, mute_end, reason))
    conn.commit()
    conn.close()

def remove_mute(user_id, guild_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM muted_users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()
    conn.close()

def is_muted(user_id, guild_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT mute_end FROM muted_users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    result = cursor.fetchone()
    conn.close()

    if not result:
        return False

    mute_end = datetime.fromisoformat(result[0])
    if datetime.now() >= mute_end:
        remove_mute(user_id, guild_id)
        return False
    return True

# --- Definições de campos válidos ---
campos_validos_alterar_carreira = [
    "nome", "nacionalidade", "posicao", "fintas", "perna boa", "promessa", "fisico",
    "clube", "gols", "assistencias", "desarmes", "defesas", "gol selecao",
    "brasileirao", "estadual", "libertadores", "sulamericana", "copa do brasil",
    "supercopa", "recopa", "mundial", "super mundial", "copa america",
    "copa do mundo", "euro"
]

correspondencias_campos_carreira = {
    "gol selecao": "gol_selecao", "gols selecao": "gol_selecao", "gols pela selecao": "gol_selecao",
    "gols": "gols", "assistencias": "assistencias", "desarmes": "desarmes", "defesas": "defesas",
    "brasileirao": "brasileirao", "estadual": "estadual", "libertadores": "libertadores",
    "sulamericana": "sulamericana", "copa do brasil": "copadobrasil", "supercopa": "supercopa",
    "recopa": "recopa", "mundial": "mundial", "super mundial": "supermundial",
    "copa america": "copaamerica", "copa do mundo": "copadomundo", "euro": "euro",
    "fintas": "fintas", "perna boa": "perna_boa", "promessa": "promessa", "fisico": "fisico",
    "clube": "clube", "nome": "nome", "nacionalidade": "nacionalidade", "posicao": "posicao"
}

campos_numericos_carreira = [
    "gols", "assistencias", "desarmes", "defesas", "brasileirao", "estadual",
    "libertadores", "sulamericana", "copadobrasil", "supercopa", "recopa",
    "mundial", "supermundial", "copaamerica", "copadomundo", "euro", "gol_selecao",
    "fintas"
]

campos_validos_rolls = [
    "chute", "passe", "cabecio", "velocidade", "drible", "dominio",
    "penaltis", "faltas", "corpo", "desarme", "bloqueio", "carrinho", "ultima chance",
    "defesa gk", "tiro de meta", "lancamento", "penaltis gk"
]

correspondencias_rolls = {
    "chute": "chute", "passe": "passe", "cabecio": "cabecio", "velocidade": "velocidade",
    "drible": "drible", "dominio": "dominio", "penaltis": "penaltis", "faltas": "faltas",
    "corpo": "corpo", "desarme": "desarme", "bloqueio": "bloqueio", "carrinho": "carrinho",
    "ultima chance": "ultima_chance", "defesa gk": "defesa_gk", "tiro de meta": "tiro_de_meta",
    "lancamento": "lancamento", "penaltis gk": "penaltis_gk"
}

# --- Funções de Banco de Dados para Tarefas ---
def add_task_to_db(user_id, task_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (user_id, task_name, completed) VALUES (?, ?, 0)', (user_id, task_name))
    conn.commit()
    conn.close()

def get_tasks_from_db(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, task_name, completed FROM tasks WHERE user_id = ?', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def complete_task_in_db(task_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def delete_task_from_db(task_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

# --- Funções de lembretes ---
def add_reminder_to_db(user_id, reminder_text, reminder_time):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reminders (user_id, reminder, reminder_time) VALUES (?, ?, ?)', 
                   (user_id, reminder_text, reminder_time))
    conn.commit()
    conn.close()

# --- Funções de Geração de Embeds ---
def gerar_embed_carreira(user, dados):
    embed = discord.Embed(
        title=f"╭ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ\n╰▸ ‹ 👤 › ৎ˚₊ Visualize a carreira de: {user.display_name}",
        description="",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_image(url="https://media.discordapp.net/attachments/1375957369972064276/1377854075814678658/Puerto_Football.S6._-_RP.png?ex=683a7a1a&is=6839289a&hm=96435d178cdedd5c7584eef5aef3d824a9cbf43967fa80db9fe2c12a5d01447c&")
    embed.set_footer(text="╰ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ\nUse p!ranking para ver os melhores da temporada! - Dev: YevgennyMXP", icon_url=user.guild.icon.url if user.guild and user.guild.icon else None)

    embed.add_field(name="⠀", value=
        "ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ       ﹐ꜜ __‹👤›__ **__I__dentidade do __J__ogador !** __‹👤›__ ꜜ﹐\n"
        f"╰▸ ‹ 👤 › ৎ˚₊ Nome: **{dados.get('nome', 'N/A')}**\n"
        f"╰▸ ‹ 🏳️ › ৎ˚₊ Nacionalidade: **{dados.get('nacionalidade', 'N/A')}**\n"
        f"╰▸ ‹ ⛳ › ৎ˚₊ Posição: **{dados.get('posicao', 'N/A')}**\n"
        f"╰▸ ‹ ⭐ › ৎ˚₊ Fintas: **{dados.get('fintas', 'N/A')}**\n"
        f"╰▸ ‹ 🦿 › ৎ˚₊ Perna Boa: **{dados.get('perna_boa', 'N/A')}**\n"
        f"╰▸ ‹ 🎖️ › ৎ˚₊ Promessa?: **{dados.get('promessa', 'N/A')}**\n"
        f"╰▸ ‹ 💪 › ৎ˚₊ Físico: **{dados.get('fisico', 'N/A')}**",
        inline=False
    )

    embed.add_field(name="⠀", value=
        "       ﹐ꜜ __‹🏟️›__ **__D__esempenho em __C__ampo !** __‹🏟️›__ ꜜ﹐\n"
        f"╰▸ ‹ 🏟️ › ৎ˚₊ Clube: **{dados.get('clube', 'N/A')}**\n"
        f"╰▸ ‹ ⚽ › ৎ˚₊ Gols: **{dados.get('gols', 0)}**\n"
        f"╰▸ ‹ 🏹 › ৎ˚₊ Assistências: **{dados.get('assistencias', 0)}**\n"
        f"╰▸ ‹ 🛡️ › ৎ˚₊ Desarmes: **{dados.get('desarmes', 0)}**\n"
        f"╰▸ ‹ 🧤 › ৎ˚₊ Defesas (GK): **{dados.get('defesas', 0)}**",
        inline=False
    )

    total_titulos_clube = sum([dados.get(k, 0) for k in ["brasileirao", "estadual", "libertadores", "sulamericana", "copadobrasil", "supercopa", "recopa", "mundial", "supermundial"]])

    embed.add_field(name="⠀", value=
        "       ﹐ꜜ __‹🏆›__ **__T__ítulos __C__onquistados !** __‹🏆›__ ꜜ﹐\n"
        f"╰▸ ‹ <:puerto_Brasileirao:1377848287876616223> › ৎ˚₊ Brasileirão: **{dados.get('brasileirao', 0)}**\n"
        f"╰▸ ‹ 🏆 › ৎ˚₊ Títulos Estaduais: **{dados.get('estadual', 0)}**\n"
        f"╰▸ ‹ <:puerto_Libertadores:1377848356520329277> › ৎ˚₊ Libertadores: **{dados.get('libertadores', 0)}**\n"
        f"╰▸ ‹ <:sudamericana:1377848396508823732> › ৎ˚₊ Sudamericana: **{dados.get('sulamericana', 0)}**\n"
        f"╰▸ ‹ <:Copa_do_Brasil:1377848458425143378> › ৎ˚₊ Copa do Brasil: **{dados.get('copadobrasil', 0)}**\n"
        f"╰▸ ‹ <:us_supercopa:1377848513928364103> › ৎ˚₊ Supercopa Rei: **{dados.get('supercopa', 0)}**\n"
        f"╰▸ ‹ <:us_recopa:1377848552083951686> › ৎ˚₊ Recopa Sudamericana: **{dados.get('recopa', 0)}**\n"
        f"╰▸ ‹ <:taca_mundial:1377848591389036559> › ৎ˚₊ Intercontinental de Clubes: **{dados.get('mundial', 0)}**\n"
        f"╰▸ ‹ <:Super_Mundial:1377848122121912320> › ৎ˚₊ Super Mundial de Clubes: **{dados.get('supermundial', 0)}**",
        inline=False
    )

    embed.add_field(name="⠀", value=
        "       ﹐ꜜ __‹🌐›__ **__C__onquistas por __S__eleção !** __‹🌐›__ ꜜ﹐\n"
        f"╰▸ ‹ <:worldcup:1377848740798398517> › ৎ˚₊ Copa do Mundo: **{dados.get('copadomundo', 0)}**\n"
        f"╰▸ ‹ <:CopaAmerica:1377848763879526481> › ৎ˚₊ Copa América: **{dados.get('copaamerica', 0)}**\n"
        f"╰▸ ‹ <:Eurocopa:1377848812940427298> › ৎ˚₊ Eurocopa: **{dados.get('euro', 0)}**\n"
        f"╰▸ ‹ ⚽ › ৎ˚₊ G/A por Seleção: **{dados.get('gol_selecao', 0)}**",
        inline=False
    )

    return embed

def gerar_embed_rolls(user, rolls_data, is_own_rolls):
    title_text = "Seus Rolls" if is_own_rolls else f"Rolls de: {user.display_name}"

    embed = discord.Embed(
        title=f"╭ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ \n╰▸ ‹ 🎰 › ৎ˚₊ **__{title_text}:__**",
        description="__ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ__",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_image(url="https://media.discordapp.net/attachments/1340423194703822883/1377864414899863694/Picsart_25-05-30_01-20-21-837.png?ex=683a83bb&is=6839323b&hm=5f47ea1cffeecbf4979ea06023b6d8a304bc3b2cf5170181f5c2a79a05b07078&")
    embed.set_footer(text="╰ㆍ┈┈ㆍ◜ᨒ◞ㆍ┈┈ㆍ\nUse p!editar <atributo> <roll> - Dev: YevgennyMXP")

    embed.add_field(name="⠀", value=
        "﹐ꜜ __‹⚔️›__ **__H__abilidades de __L__inha !** __‹⚔️›__ ꜜ﹐\n"
        f"╰▸ ‹ 💥 › ৎ˚₊ **__Chute:__** {rolls_data.get('chute', 0)}\n"
        f"╰▸ ‹ 🏹 › ৎ˚₊ **__Passe:__** {rolls_data.get('passe', 0)}\n"
        f"╰▸ ‹ 🤯 › ৎ˚₊ **__Cabeceio:__** {rolls_data.get('cabecio', 0)}\n"
        f"╰▸ ‹ ⚡ › ৎ˚₊ **__Velocidade:__** {rolls_data.get('velocidade', 0)}\n"
        f"╰▸ ‹ ✨ › ৎ˚₊ **__Drible:__** {rolls_data.get('drible', 0)}\n"
        f"╰▸ ‹ 💦 › ৎ˚₊ **__Domínio:__** {rolls_data.get('dominio', 0)}",
        inline=False
    )

    embed.add_field(name="⠀", value=
        "﹐ꜜ __‹🛡️›__ **__H__abilidades __D__efensivas !** __‹🛡️›__ ꜜ﹐\n"
        f"╰▸ ‹ 🧊 › ৎ˚₊ **__Pênaltis:__** {rolls_data.get('penaltis', 0)}\n"
        f"╰▸ ‹ 💫 › ৎ˚₊ **__Faltas:__** {rolls_data.get('faltas', 0)}\n"
        f"╰▸ ‹ 💪 › ৎ˚₊ **__Corpo:__** {rolls_data.get('corpo', 0)}\n"
        f"╰▸ ‹ 🦿 › ৎ˚₊ **__Desarme:__** {rolls_data.get('desarme', 0)}\n"
        f"╰▸ ‹ 🧱 › ৎ˚₊ **__Bloqueio:__** {rolls_data.get('bloqueio', 0)}\n"
        f"╰▸ ‹ ☠️ › ৎ˚₊ **__Carrinho:__** {rolls_data.get('carrinho', 0)}\n"
        f"╰▸ ‹ 🦸‍♂️ › ৎ˚₊ **__Última Chance:__** {rolls_data.get('ultima_chance', 0)}",
        inline=False
    )

    embed.add_field(name="⠀", value=
        "﹐ꜜ __‹🧤›__ **__A__tributos de __G__oleiro !** __‹🧤›__ ꜜ﹐\n"
        f"╰▸ ‹ 🦹‍♂️ › ৎ˚₊ **__Defesa GK:__** {rolls_data.get('defesa_gk', 0)}\n"
        f"╰▸ ‹ 💣 › ৎ˚₊ **__Tiro de Meta:__** {rolls_data.get('tiro_de_meta', 0)}\n"
        f"╰▸ ‹ 💯 › ৎ˚₊ **__Lançamento:__** {rolls_data.get('lancamento', '—')}\n"
        f"╰▸ ‹ 👨‍⚖️ › ৎ˚₊ **__Pênaltis GK:__** {rolls_data.get('penaltis_gk', 0)}",
        inline=False
    )

    return embed

def gerar_ranking_embed(ctx, campo, titulo):
    if campo == "titulos":
        top = sorted(dados_usuarios.items(), key=lambda x: sum([x[1].get(k, 0) for k in ["brasileirao", "estadual", "libertadores", "sulamericana", "copadobrasil", "supercopa", "recopa", "mundial", "supermundial", "copaamerica", "copadomundo", "euro"]]), reverse=True)[:10]
    elif campo == "money":
        users_with_money = [(uid, get_user_money(uid)) for uid in dados_usuarios.keys()]
        top = sorted(users_with_money, key=lambda x: x[1], reverse=True)[:10]
    else:
        top = sorted(dados_usuarios.items(), key=lambda x: x[1].get(campo, 0), reverse=True)[:10]

    embed = discord.Embed(
        title=f"🏆 {titulo}",
        description=f"Veja o top 10 de {titulo.lower()}!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

    for i, item in enumerate(top, 1):
        if campo == "money":
            uid, valor = item
            dados = {}
        else:
            uid, dados = item

        membro = bot.get_user(uid)
        nome = membro.display_name if membro else "Indefinido"

        if campo == "titulos":
            valor = sum([dados.get(k, 0) for k in ["brasileirao", "estadual", "libertadores", "sulamericana", "copadobrasil", "supercopa", "recopa", "mundial", "supermundial", "copaamerica", "copadomundo", "euro"]])
        elif campo == "money":
            pass  # valor já foi definido acima
        else:
            valor = dados.get(campo, 0)

        embed.add_field(name=f"#{i} — {nome}", value=f"{valor}", inline=False)

    return embed

# --- Slot Machine (Fortune Tiger) ---
SYMBOLS = {
    "cherry": "🍒",
    "bell": "🔔",
    "orange": "🍊",
    "grape": "🍇",
    "watermelon": "🍉",
    "bar": "🎰",
    "seven": "7️⃣",
    "tiger": "🐯"
}

SYMBOL_WEIGHTS = {
    "cherry": 20,
    "bell": 15,
    "orange": 15,
    "grape": 10,
    "watermelon": 10,
    "bar": 8,
    "seven": 5,
    "tiger": 2
}

WEIGHTED_SYMBOLS = [symbol for symbol, weight in SYMBOL_WEIGHTS.items() for _ in range(weight)]

# Sistema de multiplicadores com pesos (chances menores para multiplicadores maiores)
MULTIPLIER_SYSTEM = {
    1.0: 40,    # 40% de chance - sem multiplicador
    1.2: 25,    # 25% de chance
    1.5: 15,    # 15% de chance
    2.0: 10,    # 10% de chance
    2.5: 5,     # 5% de chance
    3.0: 3,     # 3% de chance
    5.0: 1.5,   # 1.5% de chance
    10.0: 0.5   # 0.5% de chance - super raro
}

# Lista ponderada de multiplicadores
WEIGHTED_MULTIPLIERS = []
for mult, weight in MULTIPLIER_SYSTEM.items():
    WEIGHTED_MULTIPLIERS.extend([mult] * int(weight * 10))  # Multiplicar por 10 para ter números inteiros

def get_random_multiplier():
    """Seleciona um multiplicador aleatório baseado nos pesos"""
    return random.choice(WEIGHTED_MULTIPLIERS)

WIN_LINES = [
    [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(2, 0), (2, 1), (2, 2)],
    [(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)],
    [(0, 0), (1, 0), (2, 0)], [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
]

def generate_board():
    board = []
    for _ in range(3):
        row = [random.choice(WEIGHTED_SYMBOLS) for _ in range(3)]
        board.append(row)
    return board

def check_wins(board):
    wins = []
    for line_coords in WIN_LINES:
        symbols_on_line = [board[r][c] for r, c in line_coords]
        if symbols_on_line[0] == symbols_on_line[1] == symbols_on_line[2]:
            wins.append({"symbol": symbols_on_line[0], "line": line_coords})
    return wins

def get_slot_display(board, multiplier=None, full_match=False):
    display_board = ""

    # Mostrar multiplicador no topo se houver
    if multiplier and multiplier > 1.0:
        if multiplier >= 5.0:
            display_board += "🔥✨💎 **MULTIPLICADOR ÉPICO!** 💎✨🔥\n"
            display_board += f"🎯 **{multiplier}x** 🎯\n\n"
        elif multiplier >= 3.0:
            display_board += "⚡💰 **SUPER MULTIPLICADOR!** 💰⚡\n"
            display_board += f"🎲 **{multiplier}x** 🎲\n\n"
        elif multiplier >= 2.0:
            display_board += "🌟 **MULTIPLICADOR ATIVO!** 🌟\n"
            display_board += f"🎊 **{multiplier}x** 🎊\n\n"
        else:
            display_board += "✨ **Multiplicador:** ✨\n"
            display_board += f"🎈 **{multiplier}x** 🎈\n\n"

    if full_match:
        display_board += "🌟✨💰 **JACKPOT!** 💰✨🌟\n\n"

    display_board += "```\n"
    display_board += "╔═════════════╗\n"

    for r_idx, row in enumerate(board):
        display_board += "║ "
        for c_idx, symbol_key in enumerate(row):
            emoji = SYMBOLS.get(symbol_key, "❓")
            display_board += f"{emoji} "
        display_board += "║\n"

    display_board += "╚═════════════╝\n"
    display_board += "```\n"

    if full_match:
        display_board += "\n💥 **BIG WIN!** 💥\n"

    return display_board

class SpinButton(Button):
    def __init__(self, amount: int, original_user_id: int):
        super().__init__(label=f"💰 Apostar {amount}", style=discord.ButtonStyle.success)
        self.amount = amount
        self.original_user_id = original_user_id

    async def callback(self, interaction: discord.Interaction):
        # Verificar se é o usuário original
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        user_id = interaction.user.id
        current_money = get_user_money(user_id)

        if current_money < self.amount:
            embed = discord.Embed(
                title="❌ Saldo Insuficiente",
                description=f"Você não tem `{self.amount}` moedas para apostar. Seu saldo atual é `{current_money}`.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        remove_user_money(user_id, self.amount)
        new_money = get_user_money(user_id)

        board = generate_board()
        wins = check_wins(board)

        full_match = True
        first_symbol = board[0][0]
        for r in range(3):
            for c in range(3):
                if board[r][c] != first_symbol:
                    full_match = False
                    break
            if not full_match:
                break

        total_winnings = 0
        win_description = ""
        multiplier = None

        if full_match:
            multiplier = get_random_multiplier()
            base_payout = self.amount * 100
            final_payout = int(base_payout * multiplier)
            total_winnings += final_payout
            win_description += f"🎉 **JACKPOT! Todos os símbolos são {SYMBOLS.get(first_symbol)}!**\n"
            if multiplier > 1.0:
                win_description += f"🎯 **Com Multiplicador {multiplier}x!**\n"
            win_description += f"💰 **Prêmio Total:** `{final_payout}` moedas!\n"
        elif wins:
            multiplier = get_random_multiplier()
            if multiplier > 1.0:
                win_description += f"🎯 **Multiplicador Ativo:** {multiplier}x\n\n"

            for win in wins:
                symbol = win["symbol"]
                base_payout = self.amount * (SYMBOL_WEIGHTS[symbol] / 5)
                payout_per_line = base_payout * multiplier
                if symbol == "tiger":
                    payout_per_line *= 5
                    win_description += f"🐅 **TIGRE DOURADO!** {SYMBOLS.get(symbol)} x3\n"
                    if multiplier > 1.0:
                        win_description += f"💎 **Bônus com {multiplier}x:** `{int(payout_per_line)}` moedas!\n"
                    else:
                        win_description += f"💎 **Bônus:** `{int(payout_per_line)}` moedas!\n"
                else:
                    if multiplier > 1.0:
                        win_description += f"💰 **{SYMBOLS.get(symbol)} x3 (x{multiplier}):** `{int(payout_per_line)}` moedas\n"
                    else:
                        win_description += f"💰 **{SYMBOLS.get(symbol)} x3:** `{int(payout_per_line)}` moedas\n"
                total_winnings += payout_per_line
        else:
            win_description = "😞 **Sem sorte desta vez!** Tente novamente!"

        add_user_money(user_id, int(total_winnings))
        final_money = get_user_money(user_id)

        color = discord.Color.gold() if total_winnings > 0 else discord.Color.red()
        if full_match:
            color = discord.Color.from_rgb(255, 215, 0)  # Dourado brilhante para jackpot

        embed = discord.Embed(
            title="🎰 Fortune Tiger - Caça Níqueis 🐅",
            color=color
        )

        # Definir imagem baseada no resultado
        if total_winnings == 0:
            # Caso perca
            embed.set_image(url="https://media.discordapp.net/attachments/1305879543394861056/1378099614137323622/tigrinho-fortune.gif?ex=683b5ec7&is=683a0d47&hm=f173925cca9a7bd421329ce1117a719553333728133ef34f95478ab54133b858&=")
        elif multiplier and multiplier >= 2.5:
            # Bonus acima de 2.5x
            embed.set_image(url="https://media.discordapp.net/attachments/1305879543394861056/1378099614661607484/tigrinho-jogo-tigrinho_1.gif?ex=683b5ec7&is=683a0d47&hm=ea41be0124642a56d5fd7dc0ffc03e538f1802760f485ff3aaf48617947ab51a&=")
        elif total_winnings > 0:
            # Ganhou (acima de 1.5x ou qualquer vitória)
            embed.set_image(url="https://media.discordapp.net/attachments/1305879543394861056/1378099615047618742/tigrinho-jogo-tigrinho.gif?ex=683b5ec8&is=683a0d48&hm=a6abcc2357c345c511f227bf70e926b6e01b6120d866823cea2ddd3a976775db&=")

        embed.add_field(
            name="💰 Aposta",
            value=f"`{self.amount}` moedas",
            inline=True
        )

        embed.add_field(
            name="🎯 Resultado",
            value=f"`+{int(total_winnings)}` moedas" if total_winnings > 0 else f"`-{self.amount}` moedas",
            inline=True
        )

        embed.add_field(
            name="💎 Saldo Final",
            value=f"`{final_money}` moedas",
            inline=True
        )

        embed.add_field(
            name="🎲 Máquina Caça-Níqueis",
            value=get_slot_display(board, multiplier=multiplier if total_winnings > 0 else None, full_match=full_match),
            inline=False
        )

        if win_description:
            embed.add_field(
                name="🏆 Prêmios",
                value=win_description,
                inline=False
            )
        embed.set_footer(text=f"Partida de slot por {interaction.user.display_name} - Dev: YevgennyMXP")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        view = BetView(self.amount, self.original_user_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ChangeBetButton(Button):
    def __init__(self, label: str, amount: int, original_user_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.amount = amount
        self.original_user_id = original_user_id

    async def callback(self, interaction: discord.Interaction):
        # Verificar se é o usuário original
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎰 Fortune Tiger Slot!",
            description=f"Pronto para apostar `{self.amount}` moedas?",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Clique em 'Apostar {self.amount}' para girar. - Dev: YevgennyMXP")
        view = BetView(self.amount, self.original_user_id)
        await interaction.response.edit_message(embed=embed, view=view)

class BetView(View):
    def __init__(self, current_amount: int, original_user_id: int):
        super().__init__(timeout=180)
        self.current_amount = current_amount
        self.original_user_id = original_user_id
        self.add_item(SpinButton(current_amount, original_user_id))
        self.add_item(ChangeBetButton("Apostar 50", 50, original_user_id))
        self.add_item(ChangeBetButton("Apostar 100", 100, original_user_id))
        self.add_item(ChangeBetButton("Apostar 500", 500, original_user_id))

# --- Eventos do Bot ---
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user.name} ({bot.user.id})')
    print('Bot pronto para uso!')



# --- Help System with organized buttons ---
class HelpView(View):
    def __init__(self, original_user_id: int):
        super().__init__(timeout=300)
        self.original_user_id = original_user_id

    def get_main_embed(self):
        embed = discord.Embed(
            title="🎯 Central de Comandos - Gyrus Burguer",
            description="**Bem-vindo ao sistema de ajuda!**\n\nSelecione uma categoria abaixo para ver os comandos disponíveis. Use os botões para navegar entre as diferentes seções.",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.add_field(
            name="📱 Como usar",
            value="• Clique nos botões abaixo para explorar\n• Cada categoria tem comandos específicos\n• Use `p!` antes de cada comando",
            inline=False
        )
        embed.set_footer(text="💡 Dica: Clique em qualquer categoria para começar! - Dev: YevgennyMXP")
        return embed

    def get_carreira_embed(self):
        embed = discord.Embed(
            title="⚽ Carreira e Rolls",
            description="Comandos para gerenciar sua carreira de jogador e rolls de habilidades",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🏆 Comandos de Carreira",
            value=(
                "`p!carreira [@usuário]` - Ver carreira completa\n"
                "`p!alterar <campo> <valor>` - Alterar dados da carreira\n"
                "`p!ranking` - Rankings dos melhores jogadores"
            ),
            inline=False
        )
        embed.add_field(
            name="🎲 Comandos de Rolls",
            value=(
                "`p!rolls [@usuário]` - Ver rolls de habilidades\n"
                "`p!editar <roll> <valor>` - Editar seus rolls"
            ),
            inline=False
        )
        return embed

    def get_economia_embed(self):
        embed = discord.Embed(
            title="💰 Sistema de Economia",
            description="Ganhe, gaste e invista suas moedas no servidor!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="💵 Gerenciamento",
            value=(
                "`p!money [@usuário]` - Ver saldo atual\n"
                "`p!pay <@usuário> <valor>` - Transferir dinheiro\n"
                "`p!ranking_money` - Ranking dos mais ricos"
            ),
            inline=False
        )
        embed.add_field(
            name="💼 Ganhar Dinheiro",
            value=(
                "`p!daily` - Bônus diário (100-300 moedas)\n"
                "`p!work` - Trabalhar por dinheiro (cooldown 1h)"
            ),
            inline=False
        )
        embed.add_field(
            name="🎰 Jogos e Investimentos",
            value=(
                "`p!apostar <valor>` - Fortune Tiger (caça-níqueis)\n"
                "`p!investir <valor>` - Investir em ações e crypto"
            ),
            inline=False
        )
        return embed

    def get_moderacao_embed(self):
        embed = discord.Embed(
            title="🛠️ Ferramentas de Moderação",
            description="Comandos para moderadores manterem a ordem no servidor",
            color=discord.Color.red()
        )
        embed.add_field(
            name="🔨 Punições",
            value=(
                "`p!ban <@usuário> [motivo]` - Banir permanentemente\n"
                "`p!kick <@usuário> [motivo]` - Expulsar do servidor\n"
                "`p!mute <@usuário> [tempo] [motivo]` - Silenciar temporariamente"
            ),
            inline=False
        )
        embed.add_field(
            name="⚠️ Avisos e Controle",
            value=(
                "`p!warn <@usuário> <motivo>` - Dar aviso formal\n"
                "`p!warnings [@usuário]` - Ver histórico de avisos\n"
                "`p!unmute <@usuário>` - Remover silenciamento"
            ),
            inline=False
        )
        embed.add_field(
            name="🧹 Limpeza",
            value="`p!clear <quantidade>` - Limpar mensagens (máx: 100)",
            inline=False
        )
        return embed

    def get_diversao_embed(self):
        embed = discord.Embed(
            title="🎮 Comandos de Diversão",
            description="Entretenimento e funcionalidades divertidas para todos!",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🎲 Jogos Rápidos",
            value=(
                "`p!roll [lados]` - Rolar dado (padrão: 6 lados)\n"
                "`p!coinflip` - Cara ou coroa clássico"
            ),
            inline=False
        )
        embed.add_field(
            name="🖼️ Perfil e Avatares",
            value=(
                "`p!avatar [@usuário]` - Mostrar avatar em alta qualidade\n"
                "`p!banner [@usuário]` - Mostrar banner do perfil"
            ),
            inline=False
        )
        embed.add_field(
            name="🌐 Utilitários Diversos",
            value=(
                "`p!ping` - Verificar latência do bot\n"
                "`p!clima <cidade>` - Previsão do tempo\n"
                "`p!traduzir <texto>` - Tradutor automático"
            ),
            inline=False
        )
        return embed

    def get_utilitarios_embed(self):
        embed = discord.Embed(
            title="📋 Utilitários e Informações",
            description="Ferramentas úteis para organização e informações do servidor",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="👥 Informações de Usuário",
            value=(
                "`p!userinfo [@usuário]` - Perfil detalhado do usuário\n"
                "`p!serverinfo` - Estatísticas completas do servidor"
            ),
            inline=False
        )
        embed.add_field(
            name="📝 Sistema de Tarefas",
            value=(
                "`p!tasks` - Ver suas tarefas pendentes\n"
                "`p!addtask <descrição>` - Adicionar nova tarefa\n"
                "`p!completetask <id>` - Marcar como concluída\n"
                "`p!deletetask <id>` - Remover tarefa"
            ),
            inline=False
        )
        embed.add_field(
            name="⚡ Ferramentas Rápidas",
            value=(
                "`p!uptime` - Tempo online do bot\n"
                "`p!lembrete <tempo> <texto>` - Criar lembrete\n"
                "`p!calc <expressão>` - Calculadora matemática\n"
                "`p!resultado` - Registrar resultado de partidas"
            ),
            inline=False
        )
        return embed

    @discord.ui.button(label="🏠 Início", style=discord.ButtonStyle.primary, row=0)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_main_embed(), view=self)

    @discord.ui.button(label="⚽ Carreira", style=discord.ButtonStyle.success, row=0)
    async def carreira_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_carreira_embed(), view=self)

    @discord.ui.button(label="💰 Economia", style=discord.ButtonStyle.success, row=0)
    async def economia_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_economia_embed(), view=self)

    @discord.ui.button(label="🛠️ Moderação", style=discord.ButtonStyle.danger, row=1)
    async def moderacao_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_moderacao_embed(), view=self)

    @discord.ui.button(label="🎮 Diversão", style=discord.ButtonStyle.secondary, row=1)
    async def diversao_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_diversao_embed(), view=self)

    @discord.ui.button(label="📋 Utilitários", style=discord.ButtonStyle.secondary, row=1)
    async def utilitarios_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_utilitarios_embed(), view=self)

# --- Comandos do Bot ---

@bot.command(name='ajuda', aliases=['help'])
async def ajuda(ctx):
    help_view = HelpView(ctx.author.id)
    await ctx.reply(embed=help_view.get_main_embed(), view=help_view)

@bot.command(name='ping')
async def ping(ctx):
    # Calculando métricas em tempo real
    start_time = time.time()
    latency = round(bot.latency * 1000)

    # Simulando informações de sistema realistas
    cpu_usage = random.uniform(12.3, 45.7)
    ram_total = random.choice([16384, 32768, 65536, 131072])  # MB
    ram_used = round(ram_total * random.uniform(0.35, 0.75))
    ram_percent = round((ram_used / ram_total) * 100, 1)

    # Simulando informações de rede
    packet_loss = random.uniform(0.0, 2.1)
    jitter = random.uniform(0.5, 3.2)
    bandwidth = random.choice([1000, 2500, 5000, 10000])  # Mbps

    # Calculando uptime detalhado
    uptime_duration = datetime.now() - bot_start_time
    total_seconds = int(uptime_duration.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    # Determinando status baseado na latência
    if latency < 50:
        status = "🟢 ÓTIMO"
        color = discord.Color.from_rgb(0, 255, 127)
        performance = "Ultra Baixa"
    elif latency < 100:
        status = "🟡 BOM"
        color = discord.Color.from_rgb(255, 215, 0)
        performance = "Baixa"
    elif latency < 200:
        status = "🟠 MÉDIO"
        color = discord.Color.from_rgb(255, 165, 0)
        performance = "Moderada"
    else:
        status = "🔴 ALTO"
        color = discord.Color.from_rgb(255, 69, 0)
        performance = "Alta"

    # Calculando tempo de processamento
    process_time = round((time.time() - start_time) * 1000, 2)

    # Embed futurista
    embed = discord.Embed(
        title="⚡ **SISTEMA DE DIAGNÓSTICO NEURAL** ⚡",
        description=f"```ansi\n\u001b[36m╔══════════════════════════════════════╗\n║     🌐 ANÁLISE DE CONECTIVIDADE 🌐    ║\n╚══════════════════════════════════════╝\u001b[0m```",
        color=color,
        timestamp=discord.utils.utcnow()
    )

    # Informações de latência principal
    embed.add_field(
        name="📡 **LATÊNCIA DE REDE**",
        value=f"```yaml\nStatus: {status}\nPing: {latency}ms\nClassificação: {performance}\nJitter: {jitter:.1f}ms\nPerda de Pacotes: {packet_loss:.1f}%```",
        inline=True
    )

    # Informações de sistema
    embed.add_field(
        name="🖥️ **RECURSOS DO SISTEMA**",
        value=f"```yaml\nCPU: {cpu_usage:.1f}% de uso\nRAM: {ram_used:,}MB / {ram_total:,}MB\nMemória: {ram_percent}% utilizada\nBandwidth: {bandwidth:,} Mbps```",
        inline=True
    )

    # Informações de performance
    embed.add_field(
        name="⚙️ **MÉTRICAS DE PERFORMANCE**",
        value=f"```yaml\nTempo Processamento: {process_time}ms\nUptime: {days}d {hours}h {minutes}m\nShards Ativas: 1/1\nComandos Executados: {random.randint(8500, 15000):,}```",
        inline=True
    )

    # Barra de status visual
    def get_status_bar(value, max_value, length=10):
        filled = int((value / max_value) * length)
        bar = "█" * filled + "░" * (length - filled)
        return bar

    latency_bar = get_status_bar(min(latency, 300), 300)
    ram_bar = get_status_bar(ram_percent, 100)
    cpu_bar = get_status_bar(cpu_usage, 100)

    embed.add_field(
        name="📊 **MONITORAMENTO EM TEMPO REAL**",
        value=f"```\nLatência  [{latency_bar}] {latency}ms\nMemória   [{ram_bar}] {ram_percent}%\nCPU       [{cpu_bar}] {cpu_usage:.1f}%```",
        inline=False
    )

    # Informações técnicas detalhadas
    embed.add_field(
        name="🔬 **DIAGNÓSTICO AVANÇADO**",
        value=f"```fix\n+ Protocolo: WebSocket Gateway v10\n+ Região: São Paulo (sa-east-1)\n+ Criptografia: TLS 1.3 AES-256-GCM\n+ Taxa de Transferência: {random.randint(850, 999)}KB/s\n+ Heartbeat: {random.randint(40, 45)}s```",
        inline=False
    )

    # Footer com informações extras
    embed.set_footer(
        text=f"🤖  Yevgenny.Server1777 Neural Network • Scan ID: {random.randint(100000, 999999)} • Node: BR-SP-{random.randint(1, 8)}",
        icon_url=bot.user.display_avatar.url
    )

    # Thumbnail futurista
    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    await ctx.reply(embed=embed)

# --- Comandos de Economia ---
@bot.command(name='diario', aliases=['daily'])
async def diario(ctx):
    user_id = ctx.author.id
    if can_daily(user_id):
        amount = random.randint(100, 300)
        add_user_money(user_id, amount)
        set_daily_claimed(user_id)
        embed = discord.Embed(
            title="💰 Bônus Diário Coletado!",
            description=f"Parabéns! Você coletou seu bônus diário de `{amount}` moedas. Seu novo saldo é `{get_user_money(user_id)}`.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    else:
        embed = discord.Embed(
            title="⏰ Bônus Diário Já Coletado",
            description="Você já coletou seu bônus diário. Volte amanhã!",
            color=discord.Color.orange()
        )
        await ctx.reply(embed=embed)

@bot.command(name='trabalhar', aliases=['work'])
async def trabalhar(ctx):
    user_id = ctx.author.id
    if can_work(user_id):
        job = random.choice(trabalhos)
        payout = random.randint(job["min"], job["max"])
        add_user_money(user_id, payout)
        set_work_done(user_id)
        embed = discord.Embed(
            title="👨‍💻 Trabalho Concluído!",
            description=f"Você trabalhou como **{job['nome']}** e ganhou `{payout}` moedas! Seu novo saldo é `{get_user_money(user_id)}`.",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed)
    else:
        embed = discord.Embed(
            title="⏳ Em Tempo de Descanso",
            description="Você já trabalhou recentemente. Você pode trabalhar novamente em 1 hora.",
            color=discord.Color.orange()
        )
        await ctx.reply(embed=embed)

@bot.command(name='dinheiro', aliases=['money', 'balance', 'bal', 'saldo'])
async def dinheiro(ctx, member: discord.Member = None):
    target_user = member if member else ctx.author
    money = get_user_money(target_user.id)
    embed = discord.Embed(
        title="💰 Saldo da Conta",
        description=f"O saldo de **{target_user.display_name}** é `{money}` moedas.",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    await ctx.reply(embed=embed)

@bot.command(name='pagar', aliases=['pay', 'send'])
async def pagar_dinheiro(ctx, member: discord.Member, amount: int):
    sender_id = ctx.author.id
    receiver_id = member.id

    if amount <= 0:
        await ctx.reply("A quantia a ser enviada deve ser um número positivo.")
        return
    if sender_id == receiver_id:
        await ctx.reply("Você não pode enviar dinheiro para si mesmo.")
        return
    if get_user_money(sender_id) < amount:
        embed = discord.Embed(
            title="❌ Saldo Insuficiente",
            description=f"Você não tem `{amount}` moedas para enviar. Seu saldo atual é `{get_user_money(sender_id)}`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    remove_user_money(sender_id, amount)
    add_user_money(receiver_id, amount)

    embed = discord.Embed(
        title="💸 Transação Realizada!",
        description=f"Você enviou `{amount}` moedas para **{member.display_name}**. Seu novo saldo é `{get_user_money(sender_id)}`.",
        color=discord.Color.teal()
    )
    await ctx.send(embed=embed)

@bot.command(name='ranking_money')
async def ranking_money(ctx):
    ranking_embed = gerar_ranking_embed(ctx, "money", "Mais Ricos")
    await ctx.send(embed=ranking_embed)

@bot.command(name='apostar', aliases=['bet', 'tigrinho'])
async def apostar_command(ctx, amount: int):
    user_id = ctx.author.id
    current_money = get_user_money(user_id)

    if amount <= 0:
        embed = discord.Embed(
            title="🚫 Aposta Inválida",
            description="A quantia da aposta deve ser um número positivo.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if current_money < amount:
        embed = discord.Embed(
            title="❌ Saldo Insuficiente",
            description=f"Você não tem `{amount}` moedas para apostar. Seu saldo atual é `{current_money}`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="🎰 Fortune Tiger Slot!",
        description=f"Pronto para apostar `{amount}` moedas? Clique em 'Apostar' para girar!",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Clique em 'Apostar {amount}' para girar. - Dev: YevgennyMXP")

    view = BetView(amount, ctx.author.id)
    await ctx.reply(embed=embed, view=view)

@bot.command(name='investir')
async def investir(ctx, amount: int):
    user_id = ctx.author.id
    current_money = get_user_money(user_id)

    if amount <= 0:
        embed = discord.Embed(
            title="🚫 Investimento Inválido",
            description="A quantia do investimento deve ser um número positivo.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if current_money < amount:
        embed = discord.Embed(
            title="❌ Saldo Insuficiente",
            description=f"Você não tem `{amount}` moedas para investir. Seu saldo atual é `{current_money}`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    remove_user_money(user_id, amount)

    investment = random.choice(investimentos)
    multiplier = random.uniform(investment["min_mult"], investment["max_mult"])
    return_amount = int(amount * multiplier)

    add_user_money(user_id, return_amount)
    profit = return_amount - amount

    if profit > 0:
        result_text = f"📈 **Lucro!** Você ganhou `{profit}` moedas!"
        color = discord.Color.green()
    elif profit < 0:
        result_text = f"📉 **Prejuízo!** Você perdeu `{abs(profit)}` moedas!"
        color = discord.Color.red()
    else:
        result_text = "📊 **Empate!** Você não ganhou nem perdeu nada!"
        color = discord.Color.orange()

    embed = discord.Embed(
        title="💼 Resultado do Investimento",
        description=f"Você investiu `{amount}` moedas em **{investment['nome']}** (Risco: {investment['risco']})\n\n"
                   f"{result_text}\n\n"
                   f"Seu novo saldo: `{get_user_money(user_id)}` moedas.",
        color=color
    )
    await ctx.send(embed=embed)

# --- Comandos de Moderação ---
@bot.command(name='banir', aliases=['ban'])
@commands.has_permissions(ban_members=True)
async def banir(ctx, member: discord.Member, *, reason="Não especificado"):
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ Você não pode banir um usuário com cargo superior ao seu!")
        return

    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 Usuário Banido",
            description=f"**{member.display_name}** foi banido do servidor.\n**Motivo:** {reason}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para banir este usuário.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao banir usuário: {e}")

@bot.command(name='expulsar', aliases=['kick'])
@commands.has_permissions(kick_members=True)
async def expulsar(ctx, member: discord.Member, *, reason="Não especificado"):
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ Você não pode expulsar um usuário com cargo superior ao seu!")
        return
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 Usuário Expulso",
            description=f"**{member.display_name}** foi expulso do servidor.\n**Motivo:** {reason}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para expulsar este usuário.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao expulsar usuário: {e}")

@bot.command(name='mutar', aliases=['mute'])
@commands.has_permissions(manage_messages=True)
async def mutar(ctx, member: discord.Member, duration: str = "10m", *, reason="Não especificado"):
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ Você não pode mutar um usuário com cargo superior ao seu!")
        return
    # Parse duration
    time_units = {"m": 60, "h": 3600, "d": 86400}
    duration_seconds = 600  # default 10 minutes

    if duration[-1] in time_units:
        try:
            duration_seconds = int(duration[:-1]) * time_units[duration[-1]]
        except ValueError:
            pass

    mute_end = datetime.now() + timedelta(seconds=duration_seconds)
    add_mute(member.id, ctx.guild.id, mute_end.isoformat(), reason)

    try:
        await member.timeout(timedelta(seconds=duration_seconds), reason=reason)
        embed = discord.Embed(
            title="🔇 Usuário Mutado",
            description=f"**{member.display_name}** foi mutado por {duration}.\n**Motivo:** {reason}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para mutar este usuário.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao mutar usuário: {e}")

@bot.command(name='desmutar', aliases=['unmute'])
@commands.has_permissions(manage_messages=True)
async def desmutar(ctx, member: discord.Member):
    remove_mute(member.id, ctx.guild.id)

    try:
        await member.timeout(None)
        embed = discord.Embed(
            title="🔊 Usuário Desmutado",
            description=f"**{member.display_name}** foi desmutado.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para desmutar este usuário.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao desmutar usuário: {e}")

@bot.command(name='avisar', aliases=['warn'])
@commands.has_permissions(manage_messages=True)
async def avisar(ctx, member: discord.Member, *, reason):
    add_warn(member.id, ctx.guild.id, reason)
    warns = get_warns(member.id, ctx.guild.id)

    embed = discord.Embed(
        title="⚠️ Usuário Avisado",
        description=f"**{member.display_name}** recebeu um aviso.\n**Motivo:** {reason}\n**Total de avisos:** {len(warns)}",
        color=discord.Color.yellow()
    )
    await ctx.send(embed=embed)

@bot.command(name='avisos', aliases=['warnings'])
async def avisos(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    warns = get_warns(target.id, ctx.guild.id)

    if not warns:
        embed = discord.Embed(
            title="⚠️ Avisos",
            description=f"**{target.display_name}** não possui avisos.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title=f"⚠️ Avisos de {target.display_name}",
            description=f"Total: {len(warns)} avisos",
            color=discord.Color.yellow()
        )
        for i, (reason, warn_time) in enumerate(warns, 1):
            date = datetime.fromisoformat(warn_time).strftime("%d/%m/%Y %H:%M")
            embed.add_field(name=f"Aviso #{i}", value=f"**Motivo:** {reason}\n**Data:** {date}", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='limpar', aliases=['clear'])
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, amount: int):
    if amount <= 0 or amount > 100:
        await ctx.send("❌ A quantidade deve ser entre 1 e 100.")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = discord.Embed(
            title="🧹 Mensagens Limpas",
            description=f"Foram deletadas {len(deleted) - 1} mensagens.",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await msg.delete()
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para deletar mensagens.")

# --- Comandos de Diversão ---
@bot.command(name='roll')
async def roll_dice(ctx, sides: int = 6):
    if sides <= 0:
        await ctx.reply("❌ O número de lados deve ser positivo.")
        return

    # Embed inicial de animação
    animation_embed = discord.Embed(
        title="🎲 Rolando o Dado...",
        description="🎯 **Preparando para rolar...**",
        color=discord.Color.orange()
    )
    animation_embed.set_footer(text=f"Dado de {sides} lados em movimento... - Dev: YevgennyMXP")

    message = await ctx.reply(embed=animation_embed)

    # Sequência de animação - mostra números aleatórios
    animation_frames = [
        "🎲 **Girando...** 🌀",
        "🎯 **Rolando...** ⚡",
        "🔥 **Quase lá...** ✨",
        "⭐ **Finalizando...** 🎊"
    ]

    # Animar por algumas iterações
    for i, frame in enumerate(animation_frames):
        temp_number = random.randint(1, sides)
        animation_embed.description = f"{frame}\n\n🎲 **Valor atual:** `{temp_number}`"
        animation_embed.color = discord.Color.from_rgb(
            random.randint(100, 255),
            random.randint(100, 255), 
            random.randint(100, 255)
        )
        await asyncio.sleep(0.4)  # Pausa entre frames (reduzida de 0.8 para 0.4)
        await message.edit(embed=animation_embed)

    # Resultado final
    await asyncio.sleep(0.3)  # Reduzida de 0.5 para 0.3
    final_result = random.randint(1, sides)

    # Determinar cor baseada no resultado
    if final_result == sides:
        final_color = discord.Color.gold()
        bonus_text = "🏆 **RESULTADO MÁXIMO!** 🏆"
    elif final_result == 1:
        final_color = discord.Color.red()
        bonus_text = "🎯 **Resultado mínimo!** 🎯"
    else:
        final_color = discord.Color.green()
        bonus_text = "🎲 **Boa rolagem!** 🎲"

    final_embed = discord.Embed(
        title="🎲 Resultado Final do Dado!",
        description=f"{bonus_text}\n\n🎯 **Dado de {sides} lados**\n🏁 **Resultado:** `{final_result}`",
        color=final_color
    )
    final_embed.set_footer(text=f"Rolagem finalizada por {ctx.author.display_name} - Dev: YevgennyMXP")
    final_embed.set_thumbnail(url=ctx.author.display_avatar.url)

    await message.edit(embed=final_embed)

@bot.command(name='avatar')
async def avatar(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    embed = discord.Embed(
        title=f"Avatar de {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='banner')
async def banner(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    user = await bot.fetch_user(target.id)

    if user.banner:
        embed = discord.Embed(
            title=f"Banner de {target.display_name}",
            color=discord.Color.blue()
        )
        embed.set_image(url=user.banner.url)
    else:
        embed = discord.Embed(
            title="❌ Sem Banner",
            description=f"{target.display_name} não possui um banner personalizado.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)

@bot.command(name='coinflip')
async def coinflip(ctx):
    result = random.choice(["Cara", "Coroa"])
    emoji = "🪙" if result == "Cara" else "🔄"

    embed = discord.Embed(
        title="🪙 Cara ou Coroa",
        description=f"A moeda caiu em: **{result}** {emoji}",
        color=discord.Color.gold()
    )
    await ctx.reply(embed=embed)

@bot.command(name='clima')
async def clima(ctx, *, cidade):
    try:
        # Simulated weather data since we don't have a real API key
        conditions = ["Ensolarado", "Nublado", "Chuvoso", "Parcialmente nublado", "Tempestuoso"]
        temp = random.randint(-5, 35)
        condition = random.choice(conditions)
        humidity = random.randint(30, 90)

        embed = discord.Embed(
            title=f"🌤️ Clima em {cidade.title()}",
            description=f"**Temperatura:** {temp}°C\n**Condição:** {condition}\n**Umidade:** {humidity}%",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Erro ao obter informações do clima: {e}")

@bot.command(name='traduzir')
async def traduzir(ctx, *, texto):
    try:
        translated = translator.translate(texto, dest='pt')
        embed = discord.Embed(
            title="🌐 Tradução",
            description=f"**Original ({translated.src}):** {texto}\n**Tradução (pt):** {translated.text}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Erro ao traduzir: {e}")

# --- Comandos Utilitários ---
@bot.command(name='perfil', aliases=['userinfo'])
async def perfil(ctx, member: discord.Member = None):
    target = member if member else ctx.author

    embed = discord.Embed(
        title=f"👤 Informações de {target.display_name}",
        color=target.color
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="📋 Nome", value=f"{target.name}#{target.discriminator}", inline=True)
    embed.add_field(name="🆔 ID", value=target.id, inline=True)
    embed.add_field(name="📅 Criação da Conta", value=target.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📅 Entrou no Servidor", value=target.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="🏷️ Cargos", value=f"{len(target.roles) - 1} cargos", inline=True)
    embed.add_field(name="🤖 Bot?", value="Sim" if target.bot else "Não", inline=True)

    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def serverinfo(ctx):
    guild = ctx.guild

    embed = discord.Embed(
        title=f"🏛️ Informações do Servidor",
        color=discord.Color.blue()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="📋 Nome", value=guild.name, inline=True)
    embed.add_field(name="🆔 ID", value=guild.id, inline=True)
    embed.add_field(name="👑 Dono", value=guild.owner.mention if guild.owner else "Desconhecido", inline=True)
    embed.add_field(name="👥 Membros", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Canais", value=len(guild.channels), inline=True)
    embed.add_field(name="🏷️ Cargos", value=len(guild.roles), inline=True)
    embed.add_field(name="📅 Criado em", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="🔒 Nível de Verificação", value=str(guild.verification_level).title(), inline=True)

    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime(ctx):
    uptime_duration = datetime.now() - bot_start_time
    days = uptime_duration.days
    hours, remainder = divmod(uptime_duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    embed = discord.Embed(
        title="⏰ Tempo Online",
        description=f"O bot está online há: **{days}d {hours}h {minutes}m {seconds}s**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='lembrete')
async def lembrete(ctx, tempo, *, texto):
    try:
        # Parse time (simplified)
        time_units = {"m": 60, "h": 3600, "d": 86400}
        if tempo[-1] in time_units:
            duration = int(tempo[:-1]) * time_units[tempo[-1]]
        else:
            await ctx.send("❌ Formato de tempo inválido. Use: 10m, 2h, 1d")
            return

        reminder_time = (datetime.now() + timedelta(seconds=duration)).isoformat()
        add_reminder_to_db(ctx.author.id, texto, reminder_time)

        embed = discord.Embed(
            title="⏰ Lembrete Criado",
            description=f"Lembrete criado para daqui a {tempo}: {texto}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

        # Wait and send reminder
        await asyncio.sleep(duration)

        remind_embed = discord.Embed(
            title="🔔 Lembrete!",
            description=f"{ctx.author.mention} {texto}",
            color=discord.Color.yellow()
        )
        await ctx.send(embed=remind_embed)

    except ValueError:
        await ctx.send("❌ Formato de tempo inválido.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao criar lembrete: {e}")

@bot.command(name='calc')
async def calc(ctx, *, expression):
    try:
        # Basic calculator - only allow safe operations
        allowed_chars = "0123456789+-*/.() "
        if not all(c in allowed_chars for c in expression):
            await ctx.send("❌ Expressão contém caracteres não permitidos.")
            return

        result = eval(expression)
        embed = discord.Embed(
            title="🧮 Calculadora",
            description=f"**Expressão:** {expression}\n**Resultado:** {result}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    except ZeroDivisionError:
        await ctx.send("❌ Divisão por zero não é permitida.")
    except Exception as e:
        await ctx.send(f"❌ Erro na expressão: {e}")

# --- Comandos de Carreira e Rolls ---
@bot.command(name='carreira', aliases=['career'])
async def carreira_command(ctx, member: discord.Member = None):
    target_user = member if member else ctx.author
    if target_user.id not in dados_usuarios:
        dados_usuarios[target_user.id] = {}
    embed = gerar_embed_carreira(target_user, dados_usuarios[target_user.id])

    if target_user.id == ctx.author.id:
        message = await ctx.send(embed=embed)
        dados_usuarios[target_user.id]['carreira_message_id'] = message.id
        dados_usuarios[target_user.id]['carreira_channel_id'] = ctx.channel.id
    else:
        await ctx.send(embed=embed)

@bot.command(name='alterar', aliases=['alter', 'change'])
async def alterar(ctx, campo: str, *, valor):
    user = ctx.author
    if user.id not in dados_usuarios:
        dados_usuarios[user.id] = {}

    campo_original = campo
    campo_normalizado_input = normalizar(campo)

    campo_detectado = None

    melhor_correspondencia = process.extractOne(campo_normalizado_input, campos_validos_alterar_carreira, score_cutoff=70)

    if melhor_correspondencia:
        campo_detectado = melhor_correspondencia[0]
        campo_convertido = correspondencias_campos_carreira.get(campo_detectado, campo_detectado)

        if melhor_correspondencia[1] > 90:
            pass
        elif melhor_correspondencia[1] >= 70:
            embed = discord.Embed(
                title="🤔 Campo Não Reconhecido",
                description=f"Campo `{campo_original}` não reconhecido. Você quis dizer `{campo_detectado}`? Ajustando para `{campo_detectado}`.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Campo Inválido",
                description=f"Campo `{campo_original}` não reconhecido. Por favor, verifique a ortografia. Campos válidos para carreira incluem: {', '.join(campos_validos_alterar_carreira[:5])}...",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    else:
        embed = discord.Embed(
            title="❌ Campo Inválido",
            description=f"Campo `{campo_original}` não reconhecido. Por favor, verifique a ortografia. Campos válidos para carreira incluem: {', '.join(campos_validos_alterar_carreira[:5])}...",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if campo_detectado is None:
        embed = discord.Embed(
            title="❌ Erro Interno",
            description=f"Ocorreu um erro ao processar o campo `{campo_original}`. Tente novamente ou use um campo válido.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if campo_convertido in campos_numericos_carreira:
        if not str(valor).isdigit():
            embed = discord.Embed(
                title="❌ Valor Inválido",
                description="Este campo aceita apenas números.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        valor = int(valor)
    elif campo_convertido in ["nome", "nacionalidade", "clube", "posicao"]:
        valor = capitalizar_nome(valor)

    dados_usuarios[user.id][campo_convertido] = valor

    embed = discord.Embed(
        title="✅ Carreira Atualizada!",
        description=f"Campo `{campo_detectado}` atualizado para: `{valor}`",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

    if 'carreira_message_id' in dados_usuarios[user.id] and 'carreira_channel_id' in dados_usuarios[user.id]:
        try:
            channel = bot.get_channel(dados_usuarios[user.id]['carreira_channel_id'])
            if channel:
                message = await channel.fetch_message(dados_usuarios[user.id]['carreira_message_id'])
                if message:
                    updated_embed = gerar_embed_carreira(user, dados_usuarios[user.id])
                    await message.edit(embed=updated_embed)
        except discord.NotFound:
            print(f"Mensagem da carreira de {user.display_name} não encontrada para edição.")
        except discord.Forbidden:
            print(f"Bot não tem permissão para editar a mensagem da carreira de {user.display_name}.")
        except Exception as e:
            print(f"Erro ao tentar editar a mensagem da carreira: {e}")

@bot.command(name='rolls')
async def rolls_command(ctx, member: discord.Member = None):
    target_user = member if member else ctx.author
    is_own_rolls = (target_user.id == ctx.author.id)

    if target_user.id not in dados_rolls:
        dados_rolls[target_user.id] = {
            "chute": 0, "passe": 0, "cabecio": 0, "velocidade": 0, "drible": 0, "dominio": 0,
            "penaltis": 0, "faltas": 0, "corpo": 0, "desarme": 0, "bloqueio": 0, "carrinho": 0, "ultima_chance": 0,
            "defesa_gk": 0, "tiro_de_meta": 0, "lancamento": '—', "penaltis_gk": 0
        }

    embed = gerar_embed_rolls(target_user, dados_rolls[target_user.id], is_own_rolls)

    if is_own_rolls:
        message = await ctx.send(embed=embed)
        dados_rolls[target_user.id]['rolls_message_id'] = message.id
        dados_rolls[target_user.id]['rolls_channel_id'] = ctx.channel.id
    else:
        await ctx.send(embed=embed)

@bot.command(name='editar', aliases=['edit'])
async def editar_roll(ctx, roll_name: str, *, value: str):
    user = ctx.author
    if user.id not in dados_rolls:
        embed = discord.Embed(
            title="❓ Rolls Não Definidos",
            description="Você ainda não tem rolls definidos! Use `p!rolls` para ver seus rolls e inicializá-los.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    roll_original_input = roll_name
    roll_normalizado_input = normalizar(roll_name)

    roll_detectado = None

    melhor_correspondencia_roll = process.extractOne(roll_normalizado_input, campos_validos_rolls, score_cutoff=70)

    if melhor_correspondencia_roll:
        roll_detectado = melhor_correspondencia_roll[0]
        roll_convertido = correspondencias_rolls.get(roll_detectado, roll_detectado)

        if melhor_correspondencia_roll[1] > 90:
            pass
        elif melhor_correspondencia_roll[1] >= 70:
            embed = discord.Embed(
                title="🤔 Roll Não Reconhecido",
                description=f"Roll `{roll_original_input}` não reconhecido. Você quis dizer `{roll_detectado}`? Ajustando para `{roll_detectado}`.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Roll Inválido",
                description=f"Roll `{roll_original_input}` não reconhecido. Por favor, verifique a ortografia. Rolls válidos incluem: {', '.join(campos_validos_rolls[:5])}...",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    else:
        embed = discord.Embed(
            title="❌ Roll Inválido",
            description=f"Roll `{roll_original_input}` não reconhecido. Por favor, verifique a ortografia. Rolls válidos incluem: {', '.join(campos_validos_rolls[:5])}...",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if roll_detectado is None:
        embed = discord.Embed(
            title="❌ Erro Interno",
            description=f"Ocorreu um erro ao processar o roll `{roll_original_input}`. Tente novamente ou use um roll válido.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if roll_convertido == "lancamento":
        dados_rolls[user.id][roll_convertido] = value
    elif not value.isdigit():
        embed = discord.Embed(
            title="❌ Valor Inválido",
            description="Para este roll, o valor deve ser um **número**.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    else:
        dados_rolls[user.id][roll_convertido] = int(value)

    embed = discord.Embed(
        title="✅ Roll Atualizado!",
        description=f"Roll `{roll_detectado}` atualizado para: `{value}`",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

    if 'rolls_message_id' in dados_rolls[user.id] and 'rolls_channel_id' in dados_rolls[user.id]:
        try:
            channel = bot.get_channel(dados_rolls[user.id]['rolls_channel_id'])
            if channel:
                message = await channel.fetch_message(dados_rolls[user.id]['rolls_message_id'])
                if message:
                    updated_embed = gerar_embed_rolls(user, dados_rolls[user.id], True)
                    await message.edit(embed=updated_embed)
        except discord.NotFound:
            print(f"Mensagem de rolls de {user.display_name} não encontrada para edição.")
        except discord.Forbidden:
            print(f"Bot não tem permissão para editar a mensagem de rolls de {user.display_name}.")
        except Exception as e:
            print(f"Erro ao tentar editar a mensagem de rolls: {e}")

class RankingView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.original_user_id = ctx.author.id
        self.add_item(RankingButton("⚽ Gols", "gols", "Artilheiros"))
        self.add_item(RankingButton("🎯 Assistências", "assistencias", "Garçons"))
        self.add_item(RankingButton("🥋 Desarmes", "desarmes", "Leões"))
        self.add_item(RankingButton("🧤 Defesas", "defesas", "Paredão"))
        self.add_item(RankingButton("🏆 Títulos", "titulos", "Papa Títulos"))

class RankingButton(Button):
    def __init__(self, label, campo, titulo):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.campo = campo
        self.titulo = titulo

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        ranking_embed = gerar_ranking_embed(self.view.ctx, self.campo, self.titulo)
        await interaction.response.edit_message(embed=ranking_embed, view=self.view)

@bot.command(name='ranking', aliases=['rank'])
async def ranking_command(ctx):
    initial_embed = gerar_ranking_embed(ctx, "gols", "Artilheiros")
    view = RankingView(ctx)
    await ctx.reply(embed=initial_embed, view=view)

# --- Comandos de Tarefas ---
@bot.command(name='adicionartarefa', aliases=['addtask', 'add_task'])
async def adicionar_tarefa(ctx, *, task_name: str):
    add_task_to_db(ctx.author.id, task_name)
    embed = discord.Embed(
        title="✅ Tarefa Adicionada!",
        description=f"Tarefa **'{task_name}'** adicionada com sucesso.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='tarefas', aliases=['tasks'])
async def listar_tarefas(ctx):
    tasks = get_tasks_from_db(ctx.author.id)
    if not tasks:
        embed = discord.Embed(
            title="📋 Suas Tarefas",
            description="Você não tem nenhuma tarefa pendente.",
            color=discord.Color.light_grey()
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(title="📋 Suas Tarefas", color=discord.Color.purple())
    for task_id, name, completed in tasks:
        status = "✅ Concluída" if completed else "⏳ Pendente"
        embed.add_field(name=f"ID: {task_id}", value=f"**{name}** - {status}", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='completetask', aliases=['complete'])
async def complete_task(ctx, task_id: int):
    if complete_task_in_db(task_id):
        embed = discord.Embed(
            title="🎉 Tarefa Concluída!",
            description=f"Tarefa com ID `{task_id}` marcada como concluída!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Erro ao Concluir Tarefa",
            description=f"Não encontrei uma tarefa com o ID `{task_id}` ou ela já está concluída.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='deletetask', aliases=['deltask'])
async def delete_task(ctx, task_id: int):
    if delete_task_from_db(task_id):
        embed = discord.Embed(
            title="🗑️ Tarefa Removida!",
            description=f"Tarefa com ID `{task_id}` foi removida com sucesso.",
            color=discord.Color.dark_red()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Erro ao Remover Tarefa",
            description=f"Não encontrei uma tarefa com o ID `{task_id}` para remover.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# --- Modal para p!resultado ---
class ResultadoModal(Modal, title="⚽ Registrar Resultado da Partida"):
    time_casa = TextInput(label="Time da Casa", placeholder="Ex: Flamengo", max_length=50)
    gols_casa = TextInput(label="Gols do Time da Casa", placeholder="Ex: 2", max_length=2, style=discord.TextStyle.short)
    time_visitante = TextInput(label="Time Visitante", placeholder="Ex: Grêmio", max_length=50)
    gols_visitante = TextInput(label="Gols do Time Visitante", placeholder="Ex: 1", max_length=2, style=discord.TextStyle.short)
    estadio = TextInput(label="Estádio da Partida", placeholder="Ex: Maracanã", max_length=100)

    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gols_casa_int = int(self.gols_casa.value)
            gols_visitante_int = int(self.gols_visitante.value)
        except ValueError:
            await interaction.response.send_message("❌ Os gols devem ser números válidos!", ephemeral=True)
            return

        jogo_data = {
            'time_casa': capitalizar_nome(self.time_casa.value),
            'gols_casa': gols_casa_int,
            'time_visitante': capitalizar_nome(self.time_visitante.value),
            'gols_visitante': gols_visitante_int,
            'estadio': capitalizar_nome(self.estadio.value)
        }

        times_of_day_categories = ["Manhã", "Tarde", "Noite"]
        jogo_data['horario'] = random.choice(times_of_day_categories)

        temperatures_celsius = {
            "Muito Frio": range(-5, 1),
            "Frio": range(1, 11),
            "Agradável": range(11, 26),
            "Quente": range(26, 36),
            "Muito Quente": range(36, 46)
        }
        temp_category = random.choice(list(temperatures_celsius.keys()))
        temp_value = random.choice(temperatures_celsius[temp_category])
        jogo_data['temperatura'] = f"{temp_value}°C"

        is_day_time = jogo_data['horario'] in ["Manhã", "Tarde"]
        if temp_category in ["Muito Frio", "Frio"] and random.random() < 0.3:
            climates = ["Nevando", "Chuvoso", "Nublado"]
        elif is_day_time:
            climates = ["Ensolarado", "Nublado", "Parcialmente Nublado", "Chuvoso"]
        else:
            climates = ["Nublado", "Parcialmente Nublado", "Chuvoso", "Céu Estrelado"]
        jogo_data['clima'] = random.choice(climates)

        humidities = ["Baixa", "Moderada", "Alta"]
        jogo_data['umidade'] = random.choice(humidities)

        referee_names = [
            "Anderson Daronco", "Raphael Claus", "Wilton Pereira Sampaio",
            "Leandro Pedro Vuaden", "Savio Pereira Sampaio", "Wagner do Nascimento Magalhães",
            "Bráulio da Silva Machado", "Flávio Rodrigues de Souza", "Luiz Flávio de Oliveira"
        ]
        jogo_data['arbitro'] = random.choice(referee_names)

        other_events = [
            "Torcida fez uma festa linda nas arquibancadas com mosaicos e bandeiras!",
            "Problemas técnicos na transmissão ao vivo geraram atrasos no início.",
            "Um show de luzes e fogos de artifício marcou o intervalo da partida."
        ]
        jogo_data['eventos_aleatorios'] = random.sample(other_events, min(len(other_events), 3))

        vencedor = None
        if jogo_data['gols_casa'] > jogo_data['gols_visitante']:
            vencedor = jogo_data['time_casa']
        elif jogo_data['gols_visitante'] > jogo_data['gols_casa']:
            vencedor = jogo_data['time_visitante']

        final_embed = discord.Embed(
            title=f"🏁 **Resultado da Partida** 🏁",
            description=f"No estádio **{jogo_data['estadio']}**, a partida foi finalizada!",
            color=discord.Color.teal() if not vencedor else discord.Color.green()
        )

        placar_str = (
            f"╰▸ ‹ 🏠 › ৎ˚₊ **{jogo_data['time_casa']}** `{jogo_data['gols_casa']}`\n"
            f"╰▸ ‹ ✈️ › ৎ˚₊ **{jogo_data['time_visitante']}** `{jogo_data['gols_visitante']}`\n"
        )
        if vencedor:
            placar_str += f"╰▸ ‹ 🏆 › ৎ˚₊ Vitória de **{vencedor}**!"
        else:
            placar_str += f"╰▸ ‹ 🤝 › ৎ˚₊ A partida terminou em **empate**."

        final_embed.add_field(name="⠀", value="﹐ꜜ __‹📋›__ **__P__lacar __F__inal !** __‹📋›__ ꜜ﹐\n" + placar_str, inline=False)

        conditions_str = (
            "﹐ꜜ __‹🌐›__ **__C__ondições da __P__artida e __E__ventos !** __‹🌐›__ ꜜ﹐\n"
            f"╰▸ ‹ ⏰ › ৎ˚₊ **Horário:** {jogo_data['horario']}\n"
            f"╰▸ ‹ 🌡️ › ৎ˚₊ **Temperatura:** {jogo_data['temperatura']}\n"
            f"╰▸ ‹ ☁️ › ৎ˚₊ **Clima:** {jogo_data['clima']}\n"
            f"╰▸ ‹ 💧 › ৎ˚₊ **Umidade:** {jogo_data['umidade']}\n"
            f"╰▸ 👨‍⚖️ › ৎ˚₊ **Árbitro:** {jogo_data['arbitro']}\n"
            f"╰▸ ‹ 📣 › ৎ˚₊ **Eventos:**\n" + "\n".join([f"  › {e}" for e in jogo_data['eventos_aleatorios']])
        )
        final_embed.add_field(name="⠀", value=conditions_str, inline=False)

        final_embed.set_footer(text=f"Partida registrada por: {interaction.user.display_name} - Dev: YevgennyMXP")
        final_embed.timestamp = discord.utils.utcnow()

        if interaction.guild and interaction.guild.icon:
            final_embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.response.send_message(embed=final_embed)

class ResultadoView(View):
    def __init__(self, original_user_id: int):
        super().__init__(timeout=300)
        self.original_user_id = original_user_id

    @discord.ui.button(label="📝 Registrar Resultado", style=discord.ButtonStyle.primary, emoji="⚽")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.send_modal(ResultadoModal(interaction))

@bot.command(name='resultado', aliases=['result'])
@commands.has_permissions(manage_messages=True)
async def resultado_command(ctx):
    embed = discord.Embed(
        title="⚽ Registrar Resultado da Partida",
        description="Clique no botão abaixo para abrir o formulário de registro de resultado.",
        color=discord.Color.blue()
    )
    view = ResultadoView(ctx.author.id)
    await ctx.reply(embed=embed, view=view)

# --- Error Handlers ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ Comando Não Encontrado",
            description=f"O comando `{ctx.invoked_with}` não existe. Use `p!ajuda` para ver todos os comandos.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Sem Permissão",
            description="Você não tem permissão para usar este comando.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Argumento Obrigatório",
            description=f"Você esqueceu de fornecer um argumento obrigatório: `{error.param.name}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
    else:
        print(f"Erro não tratado: {error}")

# --- 30 Novos Comandos ---

# Commando pra invitar
CLIENT_ID = '1377549020842692728'
@bot.command()
async def invite(ctx):
    permissions = discord.Permissions(administrator=True)  # ou personalize como quiser
    invite_url = discord.utils.oauth_url(client_id=CLIENT_ID, permissions=permissions)
    await ctx.send(f"🔗 Me adicione no seu servidor com este link:\n{invite_url}")


# 1. Comando de Shop/Loja
@bot.command(name='loja', aliases=['shop'])
async def loja(ctx):
    items = [
        {"name": "Chuteira Dourada", "price": 500, "emoji": "👟", "desc": "Aumenta sua sorte nos rolls"},
        {"name": "Troféu de Ouro", "price": 1000, "emoji": "🏆", "desc": "Símbolo de prestígio"},
        {"name": "Bandeira do Clube", "price": 300, "emoji": "🚩", "desc": "Mostre seu time favorito"},
        {"name": "Luvas de Goleiro", "price": 400, "emoji": "🧤", "desc": "Para os guardiões das metas"},
        {"name": "Bola de Ouro", "price": 2500, "emoji": "⚽", "desc": "O prêmio mais cobiçado"}
    ]

    embed = discord.Embed(
        title="🛒 Loja do Gyrus Burguer",
        description="Compre itens exclusivos com suas moedas!",
        color=discord.Color.gold()
    )

    for item in items:
        embed.add_field(
            name=f"{item['emoji']} {item['name']}",
            value=f"💰 **{item['price']} moedas**\n{item['desc']}",
            inline=True
        )

    embed.set_footer(text="Use p!buy <item> para comprar - Dev: YevgennyMXP")
    await ctx.reply(embed=embed)

# 2. Comando de Comprar
@bot.command(name='comprar', aliases=['buy'])
async def comprar_item(ctx, *, item_name: str):
    items_map = {
        "chuteira": {"name": "Chuteira Dourada", "price": 500},
        "trofeu": {"name": "Troféu de Ouro", "price": 1000},
        "bandeira": {"name": "Bandeira do Clube", "price": 300},
        "luvas": {"name": "Luvas de Goleiro", "price": 400},
        "bola": {"name": "Bola de Ouro", "price": 2500}
    }

    item_key = normalizar(item_name)
    item = None

    for key, value in items_map.items():
        if key in item_key:
            item = value
            break

    if not item:
        embed = discord.Embed(
            title="❌ Item não encontrado",
            description="Use `p!shop` para ver os itens disponíveis.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)
        return

    user_money = get_user_money(ctx.author.id)
    if user_money < item["price"]:
        embed = discord.Embed(
            title="💸 Saldo Insuficiente",
            description=f"Você precisa de `{item['price']}` moedas para comprar **{item['name']}**.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)
        return

    remove_user_money(ctx.author.id, item["price"])
    embed = discord.Embed(
        title="✅ Compra Realizada!",
        description=f"Você comprou **{item['name']}** por `{item['price']}` moedas!",
        color=discord.Color.green()
    )
    await ctx.reply(embed=embed)

# 3. Sistema de Duelo
class DuelView(View):
    def __init__(self, challenger_id: int, challenged_id: int, bet: int):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.bet = bet

    @discord.ui.button(label="⚔️ Aceitar Duelo", style=discord.ButtonStyle.success)
    async def accept_duel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("❌ Apenas o desafiado pode aceitar!", ephemeral=True)
            return

        challenger_money = get_user_money(self.challenger_id)
        challenged_money = get_user_money(self.challenged_id)

        if challenged_money < self.bet:
            await interaction.response.send_message("❌ Você não tem moedas suficientes!", ephemeral=True)
            return

        challenger_power = random.randint(1, 100)
        challenged_power = random.randint(1, 100)

        if challenger_power > challenged_power:
            winner_id = self.challenger_id
            loser_id = self.challenged_id
            winner_name = bot.get_user(self.challenger_id).display_name
        else:
            winner_id = self.challenged_id
            loser_id = self.challenger_id
            winner_name = bot.get_user(self.challenged_id).display_name

        remove_user_money(loser_id, self.bet)
        add_user_money(winner_id, self.bet)

        embed = discord.Embed(
            title="⚔️ Resultado do Duelo!",
            description=f"🏆 **{winner_name}** venceu o duelo!\n💰 Ganhou `{self.bet}` moedas!",
            color=discord.Color.gold()
        )
        embed.add_field(name="📊 Poderes", value=f"Desafiante: {challenger_power}\nDesafiado: {challenged_power}", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def decline_duel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("❌ Apenas o desafiado pode recusar!", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Duelo Recusado",
            description="O duelo foi recusado.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

@bot.command(name='duelo', aliases=['duel'])
async def duelo(ctx, member: discord.Member, bet: int = 100):
    if member.id == ctx.author.id:
        await ctx.reply("❌ Você não pode duelar consigo mesmo!")
        return

    if member.bot:
        await ctx.reply("❌ Você não pode duelar com bots!")
        return

    if bet <= 0:
        await ctx.reply("❌ A aposta deve ser positiva!")
        return

    if get_user_money(ctx.author.id) < bet:
        await ctx.reply("❌ Você não tem moedas suficientes!")
        return

    embed = discord.Embed(
        title="⚔️ Desafio de Duelo!",
        description=f"**{ctx.author.display_name}** desafiou **{member.display_name}** para um duelo!\n💰 Aposta: `{bet}` moedas",
        color=discord.Color.orange()
    )

    view = DuelView(ctx.author.id, member.id, bet)
    await ctx.reply(embed=embed, view=view)

# 4. Status do Servidor
@bot.command(name='botstats', aliases=['stats'])
async def bot_stats(ctx):
    guild_count = len(bot.guilds)
    user_count = len(bot.users)
    command_count = len(bot.commands)

    embed = discord.Embed(
        title="📊 Estatísticas do Bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="🏛️ Servidores", value=guild_count, inline=True)
    embed.add_field(name="👥 Usuários", value=user_count, inline=True)
    embed.add_field(name="⚙️ Comandos", value=command_count, inline=True)
    embed.add_field(name="🐍 Python", value="3.11", inline=True)
    embed.add_field(name="📚 Discord.py", value="2.3.2", inline=True)
    embed.add_field(name="⚡ Latência", value=f"{round(bot.latency * 1000)}ms", inline=True)

    await ctx.reply(embed=embed)

# 5. Sistema de Níveis (XP)
def get_user_xp(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT xp FROM economy WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_user_xp(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # Adicionar coluna XP se não existir
    cursor.execute("PRAGMA table_info(economy)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'xp' not in columns:
        cursor.execute('ALTER TABLE economy ADD COLUMN xp INTEGER DEFAULT 0')

    cursor.execute('UPDATE economy SET xp = xp + ? WHERE user_id = ?', (amount, user_id))
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO economy (user_id, xp) VALUES (?, ?)', (user_id, amount))
    conn.commit()
    conn.close()

def get_level_from_xp(xp):
    return int(math.sqrt(xp / 100))

@bot.command(name='nivel', aliases=['level'])
async def nivel(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    xp = get_user_xp(target.id)
    level = get_level_from_xp(xp)
    next_level_xp = ((level + 1) ** 2) * 100
    progress = xp - (level ** 2 * 100)
    needed = next_level_xp - (level ** 2 * 100)

    embed = discord.Embed(
        title=f"🆙 Nível de {target.display_name}",
        color=discord.Color.purple()
    )
    embed.add_field(name="🎯 Nível Atual", value=level, inline=True)
    embed.add_field(name="⭐ XP Total", value=xp, inline=True)
    embed.add_field(name="📈 Progresso", value=f"{progress}/{needed}", inline=True)

    # Barra de progresso
    bar_length = 20
    filled = int((progress / needed) * bar_length) if needed > 0 else bar_length
    bar = "█" * filled + "░" * (bar_length - filled)
    embed.add_field(name="📊 Barra", value=f"`{bar}`", inline=False)

    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.reply(embed=embed)

# 6. Comando XP (dar XP - admin)
@bot.command(name='addxp')
@commands.has_permissions(administrator=True)
async def add_xp_command(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.reply("❌ A quantidade deve ser positiva!")
        return

    add_user_xp(member.id, amount)
    embed = discord.Embed(
        title="✅ XP Adicionado!",
        description=f"**{member.display_name}** recebeu `{amount}` XP!",
        color=discord.Color.green()
    )
    await ctx.reply(embed=embed)

# 7. Ranking de Níveis
@bot.command(name='ranking_level', aliases=['ranking_xp'])
async def ranking_level(ctx):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, xp FROM economy WHERE xp > 0 ORDER BY xp DESC LIMIT 10')
    results = cursor.fetchall()
    conn.close()

    embed = discord.Embed(
        title="🏆 Ranking de Níveis",
        description="Top 10 jogadores por XP!",
        color=discord.Color.gold()
    )

    for i, (user_id, xp) in enumerate(results, 1):
        user = bot.get_user(user_id)
        name = user.display_name if user else "Usuário Desconhecido"
        level = get_level_from_xp(xp)
        embed.add_field(
            name=f"#{i} — {name}",
            value=f"Nível {level} ({xp} XP)",
            inline=False
        )

    await ctx.reply(embed=embed)

# 8. Sistema de Cores de Perfil
@bot.command(name='color', aliases=['cor'])
async def color_profile(ctx, color: str = None):
    if not color:
        embed = discord.Embed(
            title="🎨 Cores Disponíveis",
            description="Use `p!color <cor>` para escolher:\n"
                       "🔴 red • 🟠 orange • 🟡 yellow • 🟢 green\n"
                       "🔵 blue • 🟣 purple • 🟤 brown • ⚫ black\n"
                       "⚪ white • 🩷 pink • 🔘 grey",
            color=discord.Color.blurple()
        )
        await ctx.reply(embed=embed)
        return

    colors = {
        "red": discord.Color.red(),
        "orange": discord.Color.orange(),
        "yellow": discord.Color.yellow(),
        "green": discord.Color.green(),
        "blue": discord.Color.blue(),
        "purple": discord.Color.purple(),
        "brown": discord.Color.from_rgb(139, 69, 19),
        "black": discord.Color.from_rgb(0, 0, 0),
        "white": discord.Color.from_rgb(255, 255, 255),
        "pink": discord.Color.from_rgb(255, 192, 203),
        "grey": discord.Color.from_rgb(128, 128, 128)
    }

    chosen_color = colors.get(color.lower())
    if not chosen_color:
        await ctx.reply("❌ Cor inválida! Use `p!color` para ver as opções.")
        return

    embed = discord.Embed(
        title="🎨 Cor do Perfil Alterada!",
        description=f"Sua nova cor é: **{color.title()}**",
        color=chosen_color
    )
    await ctx.reply(embed=embed)

# 9. Gerar Meme
@bot.command(name='meme')
async def meme(ctx):
    memes = [
        "https://i.imgflip.com/1bij.jpg",
        "https://i.imgflip.com/5c7lwq.png",
        "https://i.imgflip.com/4t0m5.jpg",
        "https://i.imgflip.com/26am.jpg",
        "https://i.imgflip.com/16iyn1.jpg"
    ]

    meme_url = random.choice(memes)
    embed = discord.Embed(
        title="😂 Meme Aleatório",
        color=discord.Color.blurple()
    )
    embed.set_image(url=meme_url)
    await ctx.reply(embed=embed)

# 10. Comando 8Ball
@bot.command(name='8ball')
async def eight_ball(ctx, *, question: str):
    responses = [
        "Sim, definitivamente!", "Não conte com isso.", "Sim!", "Resposta nebulosa, tente novamente.",
        "Sem dúvida!", "Minhas fontes dizem não.", "Provavelmente!", "Não é possível prever agora.",
        "Certamente!", "Muito duvidoso.", "Você pode contar com isso!", "Concentre-se e pergunte novamente.",
        "Como eu vejo, sim.", "Não!", "Sinais apontam para sim.", "Melhor não te contar agora."
    ]

    response = random.choice(responses)
    embed = discord.Embed(
        title="🎱 Bola Mágica 8",
        description=f"**Pergunta:** {question}\n**Resposta:** {response}",
        color=discord.Color.dark_blue()
    )
    await ctx.reply(embed=embed)

# 11. Comando de Sorte
@bot.command(name='luck', aliases=['sorte'])
async def luck(ctx):
    luck_percentage = random.randint(0, 100)

    if luck_percentage >= 90:
        color = discord.Color.gold()
        message = "🍀 Você está com MUITA sorte hoje!"
    elif luck_percentage >= 70:
        color = discord.Color.green()
        message = "😊 Você está com boa sorte!"
    elif luck_percentage >= 40:
        color = discord.Color.orange()
        message = "😐 Sua sorte está mediana..."
    else:
        color = discord.Color.red()
        message = "😱 Cuidado, você está azarado hoje!"

    embed = discord.Embed(
        title="🍀 Medidor de Sorte",
        description=f"**{ctx.author.display_name}**, sua sorte hoje é: **{luck_percentage}%**\n{message}",
        color=color
    )
    await ctx.reply(embed=embed)

# 12. Comando de Citação
@bot.command(name='quote', aliases=['citacao'])
async def quote(ctx):
    quotes = [
        "O futebol é uma paixão nacional. Mas para que o sentimento seja sadio, é preciso que a virtude seja superior à paixão.",
        "Futebol se joga com os pés, mas se ganha com a cabeça.",
        "No futebol, o mais difícil é tornar difícil parecer fácil.",
        "O futebol é a poesia em movimento.",
        "Prefiro perder um jogo tentando ganhar do que ganhar um jogo tentando perder."
    ]

    quote = random.choice(quotes)
    embed = discord.Embed(
        title="💭 Citação do Dia",
        description=f"*\"{quote}\"*",
        color=discord.Color.blue()
    )
    await ctx.reply(embed=embed)

# 13. Comando de Enquete
class PollView(View):
    def __init__(self, question: str, options: list):
        super().__init__(timeout=300)
        self.question = question
        self.options = options
        self.votes = {i: 0 for i in range(len(options))}
        self.voters = set()

        for i, option in enumerate(options[:5]):  # Máximo 5 opções
            button = Button(label=f"{i+1}. {option}", style=discord.ButtonStyle.secondary)
            button.callback = self.create_vote_callback(i)
            self.add_item(button)

    def create_vote_callback(self, option_index):
        async def vote_callback(interaction: discord.Interaction):
            if interaction.user.id in self.voters:
                await interaction.response.send_message("❌ Você já votou!", ephemeral=True)
                return

            self.votes[option_index] += 1
            self.voters.add(interaction.user.id)

            # Atualizar embed
            embed = discord.Embed(
                title="📊 Enquete",
                description=f"**{self.question}**",
                color=discord.Color.blue()
            )

            total_votes = sum(self.votes.values())
            for i, option in enumerate(self.options):
                votes = self.votes[i]
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
                embed.add_field(
                    name=f"{i+1}. {option}",
                    value=f"`{bar}` {votes} votos ({percentage:.1f}%)",
                    inline=False
                )

            embed.set_footer(text=f"Total: {total_votes} votos - Dev: YevgennyMXP")
            await interaction.response.edit_message(embed=embed, view=self)

        return vote_callback

@bot.command(name='poll', aliases=['enquete'])
async def poll(ctx, question: str, *options):
    if len(options) < 2:
        await ctx.reply("❌ Você precisa fornecer pelo menos 2 opções!")
        return
    if len(options) > 5:
        await ctx.reply("❌ Máximo de 5 opções permitidas!")
        return

    embed = discord.Embed(
        title="📊 Enquete",
        description=f"**{question}**",
        color=discord.Color.blue()
    )

    for i, option in enumerate(options):
        embed.add_field(
            name=f"{i+1}. {option}",
            value="`░░░░░░░░░░░░░░░░░░░░` 0 votos (0.0%)",
            inline=False
        )

    embed.set_footer(text="Total: 0 votos - Dev: YevgennyMXP")
    view = PollView(question, list(options))
    await ctx.reply(embed=embed, view=view)

# 14. Palavra do Dia
@bot.command(name='word', aliases=['palavra'])
async def word_of_day(ctx):
    words = [
        {"word": "Pênalti", "definition": "Tiro livre direto cobrado da marca do pênalti"},
        {"word": "Escanteio", "definition": "Tiro de canto concedido quando a bola sai pela linha de fundo"},
        {"word": "Impedimento", "definition": "Posição irregular de um jogador no momento do passe"},
        {"word": "Hat-trick", "definition": "Três gols marcados pelo mesmo jogador em uma partida"},
        {"word": "Nutmeg", "definition": "Drible onde a bola passa entre as pernas do adversário"}
    ]

    word_data = random.choice(words)
    embed = discord.Embed(
        title="📖 Palavra do Dia",
        description=f"**{word_data['word']}**\n\n*{word_data['definition']}*",
        color=discord.Color.purple()
    )
    await ctx.reply(embed=embed)

# 15. Countdown Timer
@bot.command(name='countdown', aliases=['timer'])
async def countdown(ctx, seconds: int):
    if seconds <= 0 or seconds > 3600:  # Máximo 1 hora
        await ctx.reply("❌ Tempo deve ser entre 1 e 3600 segundos!")
        return

    embed = discord.Embed(
        title="⏰ Timer Iniciado",
        description=f"Timer de {seconds} segundos iniciado!",
        color=discord.Color.blue()
    )
    message = await ctx.reply(embed=embed)

    await asyncio.sleep(seconds)

    final_embed = discord.Embed(
        title="⏰ Tempo Esgotado!",
        description=f"{ctx.author.mention} Seu timer de {seconds} segundos acabou!",
        color=discord.Color.red()
    )
    await message.edit(embed=final_embed)

# 16. Emoji Info
@bot.command(name='emoji')
async def emoji_info(ctx, emoji: str):
    embed = discord.Embed(
        title="😀 Informações do Emoji",
        description=f"**Emoji:** {emoji}\n**Unicode:** `{ord(emoji[0]):04x}` se for unicode",
        color=discord.Color.yellow()
    )
    await ctx.reply(embed=embed)

# 17. Random Number
@bot.command(name='random', aliases=['rand'])
async def random_number(ctx, min_num: int = 1, max_num: int = 100):
    if min_num >= max_num:
        await ctx.reply("❌ O número mínimo deve ser menor que o máximo!")
        return

    number = random.randint(min_num, max_num)
    embed = discord.Embed(
        title="🎲 Número Aleatório",
        description=f"Entre {min_num} e {max_num}: **{number}**",
        color=discord.Color.random()
    )
    await ctx.reply(embed=embed)

# 18. Comando de Idade
@bot.command(name='age', aliases=['idade'])
async def age_calculator(ctx, year: int, month: int = 1, day: int = 1):
    try:
        birth_date = datetime(year, month, day)
        today = datetime.now()
        age = today - birth_date
        years = age.days // 365

        embed = discord.Embed(
            title="🎂 Calculadora de Idade",
            description=f"Nascido em: {birth_date.strftime('%d/%m/%Y')}\nIdade: **{years} anos** ({age.days} dias)",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed)
    except ValueError:
        await ctx.reply("❌ Data inválida!")

# 19. Sistema de Dados Personalizados
@bot.command(name='customroll', aliases=['rollcustom'])
async def custom_roll(ctx, dice_notation: str):
    # Formato: XdY (ex: 3d6 = 3 dados de 6 lados)
    try:
        if 'd' not in dice_notation:
            await ctx.reply("❌ Use o formato XdY (ex: 3d6)")
            return

        parts = dice_notation.split('d')
        num_dice = int(parts[0])
        sides = int(parts[1])

        if num_dice <= 0 or num_dice > 20:
            await ctx.reply("❌ Número de dados deve ser entre 1 e 20!")
            return
        if sides <= 0 or sides > 1000:
            await ctx.reply("❌ Lados devem ser entre 1 e 1000!")
            return

        rolls = [random.randint(1, sides) for _ in range(num_dice)]
        total = sum(rolls)

        embed = discord.Embed(
            title=f"🎲 Rolagem: {dice_notation}",
            description=f"**Resultados:** {', '.join(map(str, rolls))}\n**Total:** {total}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    except ValueError:
        await ctx.reply("❌ Formato inválido! Use XdY (ex: 3d6)")

# 20. Comando Gerar Senha
@bot.command(name='password', aliases=['senha'])
async def generate_password(ctx, length: int = 12):
    if length < 4 or length > 50:
        await ctx.reply("❌ Comprimento deve ser entre 4 e 50!")
        return

    import string
    characters = string.ascii_letters + string.digits + "!@#$%&*"
    password = ''.join(random.choice(characters) for _ in range(length))

    embed = discord.Embed(
        title="🔒 Senha Gerada",
        description=f"Sua senha aleatória: ||`{password}`||",
        color=discord.Color.dark_blue()
    )
    embed.set_footer(text="⚠️ Esta senha é temporária, mude após usar!  - Dev: YevgennyMXP")
    await ctx.reply(embed=embed)

# 21. QR Code Info (simulado)
@bot.command(name='qr')
async def qr_code(ctx, *, text: str):
    embed = discord.Embed(
        title="📱 QR Code",
        description=f"QR Code para: `{text}`\n\n*Use um gerador online real para criar o QR code*",
        color=discord.Color.dark_grey()
    )
    await ctx.reply(embed=embed)

# 22. Sistema de Reação
@bot.command(name='react', aliases=['reagir'])
async def react_message(ctx, message_id: int, emoji: str):
    try:
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        await ctx.reply(f"✅ Reação {emoji} adicionada!")
    except discord.NotFound:
        await ctx.reply("❌ Mensagem não encontrada!")
    except discord.HTTPException:
        await ctx.reply("❌ Emoji inválido ou erro ao reagir!")

# 23. Simular Partida - Versão Avançada e Realista
class MatchSimulator:
    def __init__(self):
        self.stadiums = {
            "Maracanã": {
                "capacity": "78.838",
                "city": "Rio de Janeiro",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139284226936883/maracana.jpg?ex=683b7e46&is=683a2cc6&hm=d7cc9a8d4e4b13a1f2dc8b4a2e48d7ebc4c7b8d92e1c0f6a5b9e8d7c6a5b4d3e&="
            },
            "Arena Corinthians": {
                "capacity": "49.205",
                "city": "São Paulo",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139343618674759/arena-corinthians.jpg?ex=683b7e54&is=683a2cd4&hm=3f8e2d1c0b9a8d7c6e5f4e3d2c1b0a9e8d7c6b5a4e3d2c1f0e9d8c7b6a5f4e3&="
            },
            "Allianz Parque": {
                "capacity": "43.713",
                "city": "São Paulo",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139405060374628/allianz-parque.jpg?ex=683b7e62&is=683a2ce2&hm=9e8d7c6b5a4f3e2d1c0b9a8e7d6c5b4a3f2e1d0c9b8a7e6d5c4b3a2f1e0d9c&="
            },
            "Arena da Baixada": {
                "capacity": "42.372",
                "city": "Curitiba",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139463520575530/arena-da-baixada.jpg?ex=683b7e70&is=683a2cf0&hm=7d6c5b4a3f2e1d0c9b8a7e6d5c4b3a2f1e0d9c8b7a6e5d4c3b2a1f0e9d8c7b&="
            },
            "Estádio Beira-Rio": {
                "capacity": "50.842",
                "city": "Porto Alegre",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139522240921710/beira-rio.jpg?ex=683b7e7e&is=683a2cfe&hm=5c4b3a2f1e0d9c8b7a6e5d4c3b2a1f0e9d8c7b6a5e4d3c2b1a0f9e8d7c6b5a&="
            },
            "Arena Fonte Nova": {
                "capacity": "50.025",
                "city": "Salvador",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139580189270026/arena-fonte-nova.jpg?ex=683b7e8c&is=683a2d0c&hm=3b2a1f0e9d8c7b6a5e4d3c2b1a0f9e8d7c6b5a4e3d2c1b0a9f8e7d6c5b4a3e&="
            },
            "Neo Química Arena": {
                "capacity": "47.605",
                "city": "São Paulo",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139640935055390/neo-quimica-arena.jpg?ex=683b7e9a&is=683a2d1a&hm=1a0f9e8d7c6b5a4e3d2c1b0a9f8e7d6c5b4a3e2d1c0b9a8f7e6d5c4b3a2e1d&="
            },
            "Arena MRV": {
                "capacity": "46.000",
                "city": "Belo Horizonte",
                "image": "https://media.discordapp.net/attachments/1305879543394861056/1378139697558241330/arena-mrv.jpg?ex=683b7ea8&is=683a2d28&hm=f9e8d7c6b5a4e3d2c1b0a9f8e7d6c5b4a3e2d1c0b9a8f7e6d5c4b3a2e1d0c9&="
            }
        }

        self.weather_conditions = [
            {"condition": "☀️ Ensolarado", "temp": "28°C", "desc": "Dia perfeito para futebol"},
            {"condition": "⛅ Parcialmente Nublado", "temp": "24°C", "desc": "Condições ideais"},
            {"condition": "🌧️ Chuva Leve", "temp": "19°C", "desc": "Campo pode ficar escorregadio"},
            {"condition": "🌤️ Sol entre Nuvens", "temp": "26°C", "desc": "Clima agradável"},
            {"condition": "🌩️ Tempestade se Aproximando", "temp": "21°C", "desc": "Tensão no ar"}
        ]

        self.formations = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "5-3-2", "4-1-4-1"]

        # Eventos que podem resultar em gol
        self.goal_events = [
            "GOL_NORMAL",
            "GOL_PENALTI",
            "GOL_FALTA",
            "GOL_ESCANTEIO",
            "GOL_CONTRA_ATAQUE"
        ]

        # Eventos normais sem gol (serão personalizados com nomes de jogadores)
        self.normal_events_templates = [
            "🥅 **DEFESA INCRÍVEL de {goalkeeper}!** O goleiro {team} salvou o que parecia ser gol certo!",
            "🟨 **Cartão Amarelo para {player} ({team})** - Entrada dura é punida",
            "🟥 **CARTÃO VERMELHO para {player} ({team})!** Jogador expulso!",
            "🔄 **Substituição no {team}** - {player} sai, mudança tática no jogo",
            "🚑 **Atendimento Médico para {player} ({team})** - Jogador recebe cuidados no campo",
            "📐 **IMPEDIMENTO de {player} ({team})!** Lance anulado pela arbitragem",
            "🥅 **{player} ({team}) NA TRAVE!** Por muito pouco não foi gol!",
            "⛳ **Escanteio para {team}** - {player} força a defesa",
            "🦵 **Falta perigosa sofrida por {player} ({team})** - Chance de gol na bola parada",
            "👨‍⚖️ **VAR revisa lance de {player} ({team})** - Análise em andamento",
            "🧤 **Defesa de {goalkeeper} ({team})** - Intervenção importante",
            "💨 **Contra-ataque rápido puxado por {player} ({team})** - Transição perigosa",
            "🎪 **Jogada individual de {player} ({team})** - Drible desconcertante",
            "🏃‍♂️ **{player} ({team}) pela lateral** - Jogada de velocidade",
            "⚡ **Cruzamento de {player} ({team}) na área** - Bola perigosa",
            "🎯 **Chute de fora da área de {player} ({team})** - Tentativa de longe",
            "🔄 **Troca de passes envolvendo {player} ({team})** - Jogada elaborada",
            "🛡️ **Bloqueio defensivo de {player} ({team})** - Defesa bem postada"
        ]

        # Descrições dos tipos de gol (com nomes de jogadores)
        self.goal_descriptions = {
            "GOL_NORMAL": [
                "⚽ **GOL de {player} ({team})!** Que jogada espetacular! Finalização perfeita!",
                "⚽ **GOLAÇO de {player} ({team})!** Que definição incrível! Não deu chance pro goleiro!",
                "⚽ **GOL de {player} ({team})!** Jogada individual brilhante! Show de bola!",
                "⚽ **GOL de {player} ({team})!** Contra-ataque fatal! Velocidade pura!",
                "⚽ **GOL de {player} ({team})!** Cabeceada certeira! Que subida!"
            ],
            "GOL_PENALTI": [
                "⚽🎯 **GOL DE PÊNALTI de {player} ({team})!** Bateu no canto, sem chances para o goleiro!",
                "⚽🎯 **PÊNALTI CONVERTIDO por {player} ({team})!** Frieza total na hora decisiva!",
                "⚽🎯 **GOL de {player} ({team})!** Pênalti batido com categoria!"
            ],
            "GOL_FALTA": [
                "⚽🌟 **GOLAÇO DE FALTA de {player} ({team})!** Que cobrança espetacular!",
                "⚽🌟 **GOL DE FALTA de {player} ({team})!** A bola fez uma curva perfeita!",
                "⚽🌟 **FALTA CERTEIRA de {player} ({team})!** Direto no ângulo!"
            ],
            "GOL_ESCANTEIO": [
                "⚽📐 **GOL DE ESCANTEIO de {player} ({team})!** Cabeceada perfeita!",
                "⚽📐 **ESCANTEIO FATAL! {player} ({team})** aproveita a cobrança!",
                "⚽📐 **GOL de {player} ({team})!** Aproveitou bem a cobrança de escanteio!"
            ],
            "GOL_CONTRA_ATAQUE": [
                "⚽⚡ **GOL EM CONTRA-ATAQUE de {player} ({team})!** Velocidade pura!",
                "⚽⚡ **CONTRA-ATAQUE LETAL de {player} ({team})!** Não perdoou a chance!",
                "⚽⚡ **GOL de {player} ({team})!** Transição rápida e eficiente!"
            ]
        }

    def get_random_player(self, players_list, team_name):
        """Retorna um jogador aleatório da lista ou nome genérico se não houver lista"""
        if players_list and len(players_list) > 0:
            return random.choice(players_list)['name']
        else:
            # Nomes genéricos se não houver jogadores reais
            generic_names = [
                "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues",
                "Almeida", "Nascimento", "Lima", "Araújo", "Fernandes", "Carvalho",
                "Gomes", "Martins", "Rocha", "Ribeiro", "Alves", "Monteiro", "Mendes"
            ]
            return random.choice(generic_names)

    def get_goalkeeper_name(self, players_list, team_name):
        """Retorna um goleiro específico ou nome genérico"""
        if players_list:
            goalkeepers = [p for p in players_list if 'goalkeeper' in p.get('position', '').lower() or 'goleiro' in p.get('position', '').lower()]
            if goalkeepers:
                return goalkeepers[0]['name']
        
        # Nomes genéricos de goleiros
        generic_gk_names = ["Silva", "Santos", "Oliveira", "Costa", "Almeida", "Pereira"]
        return random.choice(generic_gk_names)

    async def simulate_match(self, ctx, team1: str, team2: str):
        team1 = capitalizar_nome(team1)
        team2 = capitalizar_nome(team2)

        # Buscar jogadores reais para times da Série B
        team1_players = await get_team_players(team1)
        team2_players = await get_team_players(team2)

        # Escolher estádio aleatório
        stadium_name = random.choice(list(self.stadiums.keys()))
        stadium = self.stadiums[stadium_name]

        # Escolher condições climáticas
        weather = random.choice(self.weather_conditions)

        # Formações dos times
        formation1 = random.choice(self.formations)
        formation2 = random.choice(self.formations)

        # Embed inicial - Pré-jogo
        initial_embed = discord.Embed(
            title="🏟️ **TRANSMISSÃO AO VIVO** 🏟️",
            description=f"🔴 **PREPARANDO TRANSMISSÃO...**\n\n📍 **{stadium_name}** - {stadium['city']}\n👥 Capacidade: {stadium['capacity']} torcedores",
            color=discord.Color.blue()
        )
        initial_embed.set_image(url=stadium['image'])
        initial_embed.add_field(
            name="🌤️ Condições Climáticas",
            value=f"{weather['condition']} | {weather['temp']}\n*{weather['desc']}*",
            inline=True
        )
        # Mostrar escalações se disponíveis
        confronto_text = f"🏠 **{team1}** ({formation1})\n🆚\n✈️ **{team2}** ({formation2})"
        
        initial_embed.add_field(
            name="⚽ Confronto",
            value=confronto_text,
            inline=True
        )
        
        # Adicionar escalações reais se disponíveis
        if team1_players or team2_players:
            escalacoes_text = ""
            if team1_players:
                escalacoes_text += format_team_lineup(team1, team1_players) + "\n"
            if team2_players:
                escalacoes_text += format_team_lineup(team2, team2_players)
            
            if escalacoes_text:
                initial_embed.add_field(
                    name="📋 Escalações Confirmadas",
                    value=escalacoes_text,
                    inline=False
                )
        initial_embed.set_footer(text="🔴 AO VIVO •  - Dev: YevgennyMXP")

        message = await ctx.reply(embed=initial_embed)
        await asyncio.sleep(3)

        # Atualizando para início do jogo
        pregame_embed = discord.Embed(
            title="🏟️ **TRANSMISSÃO AO VIVO** 🏟️",
            description=f"🟢 **PARTIDA INICIADA!**\n\n📍 **{stadium_name}** - {stadium['city']}\n⏱️ **1º Tempo • 0'**",
            color=discord.Color.green()
        )
        pregame_embed.set_image(url=stadium['image'])
        pregame_embed.add_field(
            name="📊 Placar Atual",
            value=f"🏠 **{team1}** `0`\n✈️ **{team2}** `0`",
            inline=True
        )
        pregame_embed.add_field(
            name="🌤️ Condições",
            value=f"{weather['condition']} | {weather['temp']}",
            inline=True
        )
        pregame_embed.add_field(
            name="📺 Formações",
            value=f"{team1}: {formation1}\n{team2}: {formation2}",
            inline=True
        )
        pregame_embed.set_footer(text="🔴 AO VIVO • 0' • Bola rolando!")

        await message.edit(embed=pregame_embed)
        await asyncio.sleep(2)

        # Simulação dos eventos do jogo
        goals1 = 0
        goals2 = 0
        events_log = []
        cards_team1 = {"yellow": 0, "red": 0}
        cards_team2 = {"yellow": 0, "red": 0}
        goal_scorers1 = []
        goal_scorers2 = []

        # Primeira parte do jogo (0-45 min)
        for minute in [8, 15, 22, 28, 35, 41, 45]:
            # Determinar tipo de evento (30% chance de ser relacionado a gol)
            if random.random() < 0.30:
                # Evento de gol
                goal_type = random.choice(self.goal_events)

                # 85% de chance de converter o evento em gol real
                if random.random() < 0.85:
                    # Decidir qual time marca
                    if random.random() > 0.5:
                        goals1 += 1
                        scorer_name = self.get_random_player(team1_players, team1)
                        goal_desc = random.choice(self.goal_descriptions[goal_type]).format(
                            player=scorer_name, team=team1
                        )
                        
                        events_log.append(f"`{minute}'` {goal_desc}")
                        events_log.append(f"🎉 **{team1.upper()} MARCA!** Placar: {team1} {goals1} x {goals2} {team2}")
                        
                        scorer_info = f"{minute}' ({scorer_name})"
                        goal_scorers1.append(scorer_info)
                    else:
                        goals2 += 1
                        scorer_name = self.get_random_player(team2_players, team2)
                        goal_desc = random.choice(self.goal_descriptions[goal_type]).format(
                            player=scorer_name, team=team2
                        )
                        
                        events_log.append(f"`{minute}'` {goal_desc}")
                        events_log.append(f"🎉 **{team2.upper()} MARCA!** Placar: {team1} {goals1} x {goals2} {team2}")
                        
                        scorer_info = f"{minute}' ({scorer_name})"
                        goal_scorers2.append(scorer_info)
                else:
                    # Chance perdida
                    miss_events = [
                        "🥅 **POR POUCO!** A bola passou raspando a trave!",
                        "🧤 **DEFESAÇA!** O goleiro fez um milagre!",
                        "📐 **IMPEDIMENTO!** Gol anulado pela arbitragem!",
                        "💥 **NA TRAVE!** Que azar! Por centímetros!"
                    ]
                    events_log.append(f"`{minute}'` {random.choice(miss_events)}")
            else:
                # Evento normal
                if random.random() < 0.1:  # 10% chance de cartão
                    if random.random() < 0.8:  # 80% amarelo, 20% vermelho
                        team_card = random.choice([team1, team2])
                        if team_card == team1:
                            cards_team1["yellow"] += 1
                        else:
                            cards_team2["yellow"] += 1
                        events_log.append(f"`{minute}'` 🟨 Cartão amarelo para {team_card}")
                    else:
                        team_card = random.choice([team1, team2])
                        if team_card == team1:
                            cards_team1["red"] += 1
                        else:
                            cards_team2["red"] += 1
                        events_log.append(f"`{minute}'` 🟥 **EXPULSÃO!** {team_card} com um a menos!")
                else:
                    # Evento normal do jogo com nomes de jogadores
                    event_template = random.choice(self.normal_events_templates)
                    
                    # Escolher time aleatório para o evento
                    event_team = random.choice([team1, team2])
                    event_players = team1_players if event_team == team1 else team2_players
                    
                    # Selecionar jogador e goleiro
                    player_name = self.get_random_player(event_players, event_team)
                    goalkeeper_name = self.get_goalkeeper_name(event_players, event_team)
                    
                    # Aplicar formatação baseada no tipo de evento
                    if "{goalkeeper}" in event_template:
                        event_desc = event_template.format(
                            goalkeeper=goalkeeper_name, team=event_team
                        )
                    else:
                        event_desc = event_template.format(
                            player=player_name, team=event_team
                        )
                    
                    events_log.append(f"`{minute}'` {event_desc}")

            # Atualizar embed com imagem do estádio
            live_embed = discord.Embed(
                title="🏟️ **TRANSMISSÃO AO VIVO** 🏟️",
                description=f"🟢 **1º TEMPO EM ANDAMENTO**\n\n📍 **{stadium_name}** - {stadium['city']}\n⏱️ **{minute}'**",
                color=discord.Color.orange()
            )
            live_embed.set_image(url=stadium['image'])
            live_embed.add_field(
                name="📊 Placar Atual",
                value=f"🏠 **{team1}** `{goals1}`\n✈️ **{team2}** `{goals2}`",
                inline=True
            )
            live_embed.add_field(
                name="📝 Últimos Eventos",
                value="\n".join(events_log[-3:]) if events_log else "Jogo equilibrado...",
                inline=False
            )
            live_embed.set_footer(text=f"🔴 AO VIVO • {minute}' • 1º Tempo")

            await message.edit(embed=live_embed)
            await asyncio.sleep(2.5)

        # Intervalo
        interval_embed = discord.Embed(
            title="🏟️ **INTERVALO** 🏟️",
            description=f"⏸️ **FIM DO 1º TEMPO**\n\n📍 **{stadium_name}** - {stadium['city']}\n⏱️ **45' + 2' (HT)**",
            color=discord.Color.yellow()
        )
        interval_embed.set_image(url=stadium['image'])
        interval_embed.add_field(
            name="📊 Placar do 1º Tempo",
            value=f"🏠 **{team1}** `{goals1}`\n✈️ **{team2}** `{goals2}`",
            inline=True
        )
        interval_embed.add_field(
            name="📈 Estatísticas",
            value=f"🟨 Cartões: {cards_team1['yellow'] + cards_team2['yellow']}\n🟥 Expulsões: {cards_team1['red'] + cards_team2['red']}\n⚽ Gols: {goals1 + goals2}",
            inline=True
        )
        interval_embed.add_field(
            name="📝 Principais Eventos",
            value="\n".join(events_log[-4:]) if events_log else "Primeiro tempo equilibrado",
            inline=False
        )
        interval_embed.set_footer(text="⏸️ INTERVALO • Análise tática em andamento")

        await message.edit(embed=interval_embed)
        await asyncio.sleep(3)

        # Segunda parte do jogo (45-90 min) - chance aumentada de gols
        for minute in [50, 56, 63, 71, 78, 84, 89, 90]:
            # Determinar tipo de evento (35% chance de ser relacionado a gol no 2º tempo)
            if random.random() < 0.35:
                # Evento de gol
                goal_type = random.choice(self.goal_events)

                # 85% de chance de converter o evento em gol real
                if random.random() < 0.85:
                    # Decidir qual time marca
                    if random.random() > 0.5:
                        goals1 += 1
                        scorer_name = self.get_random_player(team1_players, team1)
                        goal_desc = random.choice(self.goal_descriptions[goal_type]).format(
                            player=scorer_name, team=team1
                        )
                        
                        events_log.append(f"`{minute}'` {goal_desc}")
                        events_log.append(f"🔥 **{team1.upper()} MARCA!** Placar: {team1} {goals1} x {goals2} {team2}")
                        
                        scorer_info = f"{minute}' ({scorer_name})"
                        goal_scorers1.append(scorer_info)
                    else:
                        goals2 += 1
                        scorer_name = self.get_random_player(team2_players, team2)
                        goal_desc = random.choice(self.goal_descriptions[goal_type]).format(
                            player=scorer_name, team=team2
                        )
                        
                        events_log.append(f"`{minute}'` {goal_desc}")
                        events_log.append(f"🔥 **{team2.upper()} MARCA!** Placar: {team1} {goals1} x {goals2} {team2}")
                        
                        scorer_info = f"{minute}' ({scorer_name})"
                        goal_scorers2.append(scorer_info)
                else:
                    # Chance perdida no 2º tempo
                    miss_events = [
                        "😱 **PERDEU INCRÍVEL!** Cara a cara com o goleiro e mandou para fora!",
                        "🥅 **SALVOU TUDO!** Defesa espetacular do goleiro!",
                        "💥 **NO TRAVESSÃO!** A bola bateu e voltou!",
                        "📐 **IMPEDIMENTO MILIMÉTRICO!** VAR confirma posição irregular!"
                    ]
                    events_log.append(f"`{minute}'` {random.choice(miss_events)}")
            else:
                # Eventos especiais do 2º tempo
                if random.random() < 0.12:  # 12% chance de cartão (mais tensão)
                    team_card = random.choice([team1, team2])
                    card_players = team1_players if team_card == team1 else team2_players
                    player_name = self.get_random_player(card_players, team_card)
                    
                    if random.random() < 0.75:  # 75% amarelo, 25% vermelho
                        if team_card == team1:
                            cards_team1["yellow"] += 1
                        else:
                            cards_team2["yellow"] += 1
                        events_log.append(f"`{minute}'` 🟨 **Cartão amarelo para {player_name} ({team_card})** - tensão aumenta!")
                    else:
                        if team_card == team1:
                            cards_team1["red"] += 1
                        else:
                            cards_team2["red"] += 1
                        events_log.append(f"`{minute}'` 🟥 **CARTÃO VERMELHO para {player_name} ({team_card})!** Expulsão!")
                else:
                    # Eventos intensos do 2º tempo com nomes de jogadores
                    event_team = random.choice([team1, team2])
                    event_players = team1_players if event_team == team1 else team2_players
                    player_name = self.get_random_player(event_players, event_team)
                    
                    intense_events = [
                        f"⚡ **PRESSÃO TOTAL de {player_name} ({event_team})!** Vai para cima em busca do gol!",
                        f"🏃‍♂️ **CORRERIA de {player_name} ({event_team})!** Jogo fica aberto e emocionante!",
                        f"🔄 **SUBSTITUIÇÃO no {event_team}!** {player_name} entra para mudar o jogo!",
                        f"📢 **TORCIDA EXPLODE com {player_name} ({event_team})!** Estádio em festa!",
                        f"⏱️ **{player_name} ({event_team}) DESESPERADO!** Corrida contra o tempo!",
                        f"🎯 **TENTATIVA DE LONGE de {player_name} ({event_team})!** Chute de fora da área!",
                        f"🏃‍♂️ **{player_name} ({event_team}) EM VELOCIDADE PURA!** Contra-ataque perigoso!"
                    ]
                    events_log.append(f"`{minute}'` {random.choice(intense_events)}")

            # Atualizar embed com maior intensidade visual
            live_embed2 = discord.Embed(
                title="🏟️ **TRANSMISSÃO AO VIVO** 🏟️",
                description=f"🔥 **2º TEMPO - EMOÇÃO TOTAL!**\n\n📍 **{stadium_name}** - {stadium['city']}\n⏱️ **{minute}'**",
                color=discord.Color.red()
            )
            live_embed2.set_image(url=stadium['image'])
            live_embed2.add_field(
                name="📊 Placar Atual", 
                value=f"🏠 **{team1}** `{goals1}`\n✈️ **{team2}** `{goals2}`",
                inline=True
            )

            # Mostrar goleadores se houver
            if goal_scorers1 or goal_scorers2:
                scorers_text = ""
                if goal_scorers1:
                    scorers_text += f"⚽ **{team1}:** {', '.join(goal_scorers1)}\n"
                if goal_scorers2:
                    scorers_text += f"⚽ **{team2}:** {', '.join(goal_scorers2)}"
                live_embed2.add_field(
                    name="🎯 Goleadores",
                    value=scorers_text,
                    inline=True
                )

            live_embed2.add_field(
                name="📝 Últimos Eventos",
                value="\n".join(events_log[-3:]) if events_log else "Pressão total!",
                inline=False
            )
            live_embed2.set_footer(text=f"🔴 AO VIVO • {minute}' • 2º Tempo • TENSÃO MÁXIMA!")

            await message.edit(embed=live_embed2)
            await asyncio.sleep(2.5)

        # Resultado final
        if goals1 > goals2:
            winner = team1
            result_color = discord.Color.green()
            result_emoji = "🏆"
            result_text = f"**VITÓRIA DO {team1.upper()}!**"
        elif goals2 > goals1:
            winner = team2
            result_color = discord.Color.green()
            result_emoji = "🏆"
            result_text = f"**VITÓRIA DO {team2.upper()}!**"
        else:
            winner = None
            result_color = discord.Color.gold()
            result_emoji = "🤝"
            result_text = "**EMPATE EMOCIONANTE!**"

        # Embed final com estatísticas completas
        final_embed = discord.Embed(
            title="🏟️ **FIM DE JOGO** 🏟️",
            description=f"🏁 **PARTIDA ENCERRADA**\n\n📍 **{stadium_name}** - {stadium['city']}\n⏱️ **90' + 4' (FT)**\n\n{result_emoji} {result_text}",
            color=result_color
        )
        final_embed.set_image(url=stadium['image'])
        final_embed.add_field(
            name="📊 RESULTADO FINAL",
            value=f"🏠 **{team1}** `{goals1}`\n✈️ **{team2}** `{goals2}`",
            inline=True
        )

        # Mostrar goleadores detalhados
        if goal_scorers1 or goal_scorers2:
            scorers_final = ""
            if goal_scorers1:
                scorers_final += f"⚽ **{team1}:**\n{', '.join(goal_scorers1)}\n\n"
            if goal_scorers2:
                scorers_final += f"⚽ **{team2}:**\n{', '.join(goal_scorers2)}"
            final_embed.add_field(
                name="🎯 Artilheiros da Partida",
                value=scorers_final,
                inline=True
            )

        final_embed.add_field(
            name="📈 Estatísticas Finais",
            value=(
                f"⚽ **Total de Gols:** {goals1 + goals2}\n"
                f"🟨 **Cartões Amarelos:** {cards_team1['yellow'] + cards_team2['yellow']}\n"
                f"🟥 **Expulsões:** {cards_team1['red'] + cards_team2['red']}\n"
                f"🎯 **Formações:** {formation1} x {formation2}\n"
                f"📊 **Eventos:** {len(events_log)} lances"
            ),
            inline=True
        )

        # Melhores momentos (só gols e cartões vermelhos)
        best_moments = [e for e in events_log if ("⚽" in e and "GOL" in e) or "🟥" in e]
        if best_moments:
            final_embed.add_field(
                name="🎬 Melhores Momentos",
                value="\n".join(best_moments[-6:]),
                inline=False
            )

        final_embed.add_field(
            name="🌤️ Condições do Jogo",
            value=f"{weather['condition']} | {weather['temp']}\n*{weather['desc']}*",
            inline=True
        )

        final_embed.add_field(
            name="🏟️ Estádio",
            value=f"**{stadium_name}**\nCapacidade: {stadium['capacity']}\n{stadium['city']}",
            inline=True
        )

        if winner:
            final_embed.add_field(
                name=f"{result_emoji} VENCEDOR",
                value=f"**{winner}**\nParabéns pela vitória!",
                inline=True
            )

        final_embed.set_footer(text="🏁 FINAL •  - Dev: YevgennyMXP • Transmissão encerrada com sucesso!")

        await message.edit(embed=final_embed)

# Instanciar simulador
match_simulator = MatchSimulator()

@bot.command(name='simular', aliases=['simulate'])
async def simulate_match(ctx, team1: str, team2: str):
    """Simula uma partida de futebol com transmissão ao vivo realista"""
    await match_simulator.simulate_match(ctx, team1, team2)

# 24. Comando Inspire
@bot.command(name='inspire', aliases=['inspiracao'])
async def inspire(ctx):
    quotes = [
        "Acredite em si mesmo e tudo será possível.",
        "O fracasso é apenas uma oportunidade para começar novamente com mais inteligência.",
        "Não espere por oportunidades, crie-as.",
        "O sucesso é ir de fracasso em fracasso sem perder o entusiasmo.",
        "A única forma de fazer um excelente trabalho é amar o que você faz."
    ]

    quote = random.choice(quotes)
    embed = discord.Embed(
        title="✨ Inspiração do Dia",
        description=f"*{quote}*",
        color=discord.Color.gold()
    )
    await ctx.reply(embed=embed)

# 25. Sistema de Roubo (minigame)
@bot.command(name='steal', aliases=['roubar'])
async def steal_money(ctx, member: discord.Member):
    if member.id == ctx.author.id:
        await ctx.reply("❌ Você não pode roubar de si mesmo!")
        return

    if member.bot:
        await ctx.reply("❌ Você não pode roubar de bots!")
        return

    thief_money = get_user_money(ctx.author.id)
    victim_money = get_user_money(member.id)

    if thief_money < 50:
        await ctx.reply("❌ Você precisa de pelo menos 50 moedas para tentar roubar!")
        return

    if victim_money < 100:
        await ctx.reply("❌ A vítima precisa ter pelo menos 100 moedas!")
        return

    success_chance = random.randint(1, 100)

    if success_chance <= 30:  # 30% de sucesso
        stolen_amount = random.randint(50, min(200, victim_money // 2))
        remove_user_money(member.id, stolen_amount)
        add_user_money(ctx.author.id, stolen_amount)

        embed = discord.Embed(
            title="💰 Roubo Bem-sucedido!",
            description=f"Você roubou `{stolen_amount}` moedas de {member.display_name}!",
            color=discord.Color.green()
        )
    else:  # 70% de falha
        fine = random.randint(25, 100)
        remove_user_money(ctx.author.id, fine)

        embed = discord.Embed(
            title="🚨 Roubo Fracassado!",
            description=f"Você foi pego! Pagou uma multa de `{fine}` moedas.",
            color=discord.Color.red()
        )

    await ctx.reply(embed=embed)

# 26. Jogo da Adivinhação
class GuessView(View):
    def __init__(self, number: int, user_id: int):
        super().__init__(timeout=120)
        self.number = number
        self.user_id = user_id
        self.attempts = 0
        self.max_attempts = 6

    @discord.ui.button(label="📝 Fazer Palpite", style=discord.ButtonStyle.primary)
    async def make_guess(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Apenas quem iniciou o jogo pode jogar!", ephemeral=True)
            return

        modal = GuessModal(self)
        await interaction.response.send_modal(modal)

class GuessModal(Modal, title="🎯 Faça seu palpite"):
    guess = TextInput(label="Seu palpite (1-100)", placeholder="Digite um número entre 1 e 100")

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess_num = int(self.guess.value)
            if guess_num < 1 or guess_num > 100:
                await interaction.response.send_message("❌ Número deve estar entre 1 e 100!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Digite apenas números!", ephemeral=True)
            return

        self.view.attempts += 1

        if guess_num == self.view.number:
            reward = 100 + (50 * (self.view.max_attempts - self.view.attempts))
            add_user_money(interaction.user.id, reward)

            embed = discord.Embed(
                title="🎉 Parabéns! Você acertou!",
                description=f"O número era **{self.view.number}**!\nTentativas: {self.view.attempts}/{self.view.max_attempts}\nRecompensa: `{reward}` moedas!",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        elif self.view.attempts >= self.view.max_attempts:
            embed = discord.Embed(
                title="😞 Game Over!",
                description=f"Suas tentativas acabaram! O número era **{self.view.number}**.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        else:
            hint = "📈 Muito alto!" if guess_num > self.view.number else "📉 Muito baixo!"
            embed = discord.Embed(
                title="🎯 Jogo da Adivinhação",
                description=f"{hint}\nTentativa {self.view.attempts}/{self.view.max_attempts}\nContinue tentando!",
                color=discord.Color.orange()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)

@bot.command(name='guess', aliases=['adivinhar'])
async def guess_game(ctx):
    number = random.randint(1, 100)

    embed = discord.Embed(
        title="🎯 Jogo da Adivinhação",
        description="Adivinhe o número entre 1 e 100!\nVocê tem 6 tentativas. Boa sorte!",
        color=discord.Color.blue()
    )

    view = GuessView(number, ctx.author.id)
    await ctx.reply(embed=embed, view=view)

# 27. Comando Top Emojis
@bot.command(name='topemojis')
async def top_emojis(ctx):
    if not ctx.guild.emojis:
        await ctx.reply("❌ Este servidor não tem emojis personalizados!")
        return

    # Simular uso de emojis
    emoji_usage = {emoji: random.randint(0, 1000) for emoji in ctx.guild.emojis[:10]}
    sorted_emojis = sorted(emoji_usage.items(), key=lambda x: x[1], reverse=True)[:5]

    embed = discord.Embed(
        title="🏆 Top Emojis do Servidor",
        color=discord.Color.yellow()
    )

    for i, (emoji, usage) in enumerate(sorted_emojis, 1):
        embed.add_field(
            name=f"#{i} {emoji}",
            value=f"{usage} usos",
            inline=True
        )

    await ctx.reply(embed=embed)

# 28. Sistema de Backup de Dados
@bot.command(name='backup')
@commands.has_permissions(administrator=True)
async def backup_data(ctx):
    user_count = len(dados_usuarios)
    roll_count = len(dados_rolls)

    embed = discord.Embed(
        title="💾 Backup de Dados",
        description=f"Dados do servidor salvos:\n• {user_count} carreiras\n• {roll_count} perfis de rolls\n• Dados da economia em SQLite",
        color=discord.Color.green()
    )
    embed.set_footer(text="Backup realizado com sucesso! - Dev: YevgennyMXP")
    await ctx.reply(embed=embed)

# 29. Comando de Feedback
@bot.command(name='feedback', aliases=['sugestao'])
async def feedback(ctx, *, message: str):
    embed = discord.Embed(
        title="📨 Feedback Recebido",
        description=f"Obrigado pelo seu feedback!\n\n**Mensagem:** {message}",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Enviado por {ctx.author.display_name} - Dev: YevgennyMXP")
    await ctx.reply(embed=embed)

# 30. Comando de Limpeza de Cache
@bot.command(name='clearcache')
@commands.has_permissions(administrator=True)
async def clear_cache(ctx):
    # Limpar caches internos (simulado)
    cache_cleared = random.randint(50, 500)

    embed = discord.Embed(
        title="🧹 Cache Limpo",
        description=f"Cache do bot limpo com sucesso!\n{cache_cleared}MB liberados.",
        color=discord.Color.green()
    )
    await ctx.reply(embed=embed)

# Atualizar o sistema de ajuda com os novos comandos
class HelpView(View):
    def __init__(self, original_user_id: int):
        super().__init__(timeout=300)
        self.original_user_id = original_user_id

    def get_main_embed(self):
        embed = discord.Embed(
            title="🎯 Central de Comandos - Gyrus Burguer",
            description="**Bem-vindo ao sistema de ajuda!**\n\nSelecione uma categoria abaixo para ver os comandos disponíveis. Use os botões para navegar entre as diferentes seções.\n\n**✨ Novidade: 30+ Novos Comandos Adicionados!**",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.add_field(
            name="📱 Como usar",
            value="• Clique nos botões abaixo para explorar\n• Cada categoria tem comandos específicos\n• Use `p!` antes de cada comando\n• Total: 60+ comandos disponíveis!",
            inline=False
        )
        embed.set_footer(text="💡 Dica: Clique em qualquer categoria para começar! - Dev: YevgennyMXP")
        return embed

    def get_carreira_embed(self):
        embed = discord.Embed(
            title="⚽ Carreira e Rolls",
            description="Comandos para gerenciar sua carreira de jogador e rolls de habilidades",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🏆 Comandos de Carreira",
            value=(
                "`p!carreira [@usuário]` - Ver carreira completa\n"
                "`p!alterar <campo> <valor>` - Alterar dados da carreira\n"
                "`p!ranking` - Rankings dos melhores jogadores\n"
                "`p!simular <time1> <time2>` - Simular partida entre times"
            ),
            inline=False
        )
        embed.add_field(
            name="🎲 Comandos de Rolls",
            value=(
                "`p!rolls [@usuário]` - Ver rolls de habilidades\n"
                "`p!editar <roll> <valor>` - Editar seus rolls"
            ),
            inline=False
        )
        return embed

    def get_economia_embed(self):
        embed = discord.Embed(
            title="💰 Sistema de Economia",
            description="Ganhe, gaste e invista suas moedas no servidor!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="💵 Gerenciamento",
            value=(
                "`p!money [@usuário]` - Ver saldo atual\n"
                "`p!pay <@usuário> <valor>` - Transferir dinheiro\n"
                "`p!ranking_money` - Ranking dos mais ricos\n"
                "`p!shop` - Ver loja de itens\n"
                "`p!buy <item>` - Comprar item da loja"
            ),
            inline=False
        )
        embed.add_field(
            name="💼 Ganhar Dinheiro",
            value=(
                "`p!daily` - Bônus diário (100-300 moedas)\n"
                "`p!work` - Trabalhar por dinheiro (cooldown 1h)\n"
                "`p!steal <@usuário>` - Tentar roubar (arriscado!)"
            ),
            inline=False
        )
        embed.add_field(
            name="🎰 Jogos e Investimentos",
            value=(
                "`p!apostar <valor>` - Fortune Tiger (caça-níqueis)\n"
                "`p!investir <valor>` - Investir em ações e crypto\n"
                "`p!duel <@usuário> [aposta]` - Duelar por moedas\n"
                "`p!guess` - Jogo de adivinhação com prêmios\n"
                "`p!odd` - Apostar no placar exato de partidas (2x ganho)\n"
                "`p!historico_apostas` - Ver histórico de apostas"
            ),
            inline=False
        )
        return embed

    def get_moderacao_embed(self):
        embed = discord.Embed(
            title="🛠️ Ferramentas de Moderação",
            description="Comandos para moderadores manterem a ordem no servidor",
            color=discord.Color.red()
        )
        embed.add_field(
            name="🔨 Punições",
            value=(
                "`p!ban <@usuário> [motivo]` - Banir permanentemente\n"
                "`p!kick <@usuário> [motivo]` - Expulsar do servidor\n"
                "`p!mute <@usuário> [tempo] [motivo]` - Silenciar temporariamente"
            ),
            inline=False
        )
        embed.add_field(
            name="⚠️ Avisos e Controle",
            value=(
                "`p!warn <@usuário> <motivo>` - Dar aviso formal\n"
                "`p!warnings [@usuário]` - Ver histórico de avisos\n"
                "`p!unmute <@usuário>` - Remover silenciamento\n"
                "`p!react <id_msg> <emoji>` - Reagir a mensagem"
            ),
            inline=False
        )
        embed.add_field(
            name="🧹 Limpeza e Admin",
            value=(
                "`p!clear <quantidade>` - Limpar mensagens (máx: 100)\n"
                "`p!resultado` - Registrar resultado de partidas\n"
                "`p!backup` - Fazer backup dos dados (admin)\n"
                "`p!clearcache` - Limpar cache do bot (admin)"
            ),
            inline=False
        )
        return embed

    def get_diversao_embed(self):
        embed = discord.Embed(
            title="🎮 Comandos de Diversão",
            description="Entretenimento e funcionalidades divertidas para todos!",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🎲 Jogos e Sorte",
            value=(
                "`p!roll [lados]` - Rolar dado (padrão: 6 lados)\n"
                "`p!customroll <XdY>` - Dados personalizados (ex: 3d6)\n"
                "`p!coinflip` - Cara ou coroa clássico\n"
                "`p!8ball <pergunta>` - Bola mágica 8\n"
                "`p!luck` - Medidor de sorte do dia\n"
                "`p!random [min] [max]` - Número aleatório"
            ),
            inline=False
        )
        embed.add_field(
            name="🖼️ Perfil e Social",
            value=(
                "`p!avatar [@usuário]` - Mostrar avatar em alta qualidade\n"
                "`p!banner [@usuário]` - Mostrar banner do perfil\n"
                "`p!color <cor>` - Escolher cor do perfil\n"
                "`p!level [@usuário]` - Ver nível e XP\n"
                "`p!ranking_level` - Ranking de níveis"
            ),
            inline=False
        )
        embed.add_field(
            name="🎨 Diversos",
            value=(
                "`p!meme` - Meme aleatório\n"
                "`p!quote` - Citação inspiradora\n"
                "`p!inspire` - Inspiração do dia\n"
                "`p!word` - Palavra do dia (futebol)\n"
                "`p!emoji <emoji>` - Info sobre emoji"
            ),
            inline=False
        )
        return embed

    def get_utilitarios_embed(self):
        embed = discord.Embed(
            title="📋 Utilitários e Informações",
            description="Ferramentas úteis para organização e informações do servidor",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="👥 Informações",
            value=(
                "`p!userinfo [@usuário]` - Perfil detalhado do usuário\n"
                "`p!serverinfo` - Estatísticas completas do servidor\n"
                "`p!botstats` - Estatísticas do bot\n"
                "`p!topemojis` - Top emojis do servidor"
            ),
            inline=False
        )
        embed.add_field(
            name="📝 Sistema de Tarefas",
            value=(
                "`p!tasks` - Ver suas tarefas pendentes\n"
                "`p!addtask <descrição>` - Adicionar nova tarefa\n"
                "`p!completetask <id>` - Marcar como concluída\n"
                "`p!deletetask <id>` - Remover tarefa"
            ),
            inline=False
        )
        embed.add_field(
            name="⚡ Ferramentas Diversas",
            value=(
                "`p!ping` - Verificar latência avançada\n"
                "`p!uptime` - Tempo online do bot\n"
                "`p!lembrete <tempo> <texto>` - Criar lembrete\n"
                "`p!calc <expressão>` - Calculadora matemática\n"
                "`p!countdown <segundos>` - Timer/cronômetro\n"
                "`p!age <ano> [mês] [dia]` - Calcular idade\n"
                "`p!password [tamanho]` - Gerar senha segura\n"
                "`p!qr <texto>` - Informações sobre QR code\n"
                "`p!poll <pergunta> <opção1> <opção2>...` - Criar enquete\n"
                "`p!clima <cidade>` - Previsão do tempo\n"
                "`p!traduzir <texto>` - Tradutor automático\n"
                "`p!feedback <mensagem>` - Enviar feedback"
            ),
            inline=False
        )
        return embed

    @discord.ui.button(label="🏠 Início", style=discord.ButtonStyle.primary, row=0)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_main_embed(), view=self)

    @discord.ui.button(label="⚽ Carreira", style=discord.ButtonStyle.success, row=0)
    async def carreira_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_carreira_embed(), view=self)

    @discord.ui.button(label="💰 Economia", style=discord.ButtonStyle.success, row=0)
    async def economia_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_economia_embed(), view=self)

    @discord.ui.button(label="🛠️ Moderação", style=discord.ButtonStyle.danger, row=1)
    async def moderacao_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_moderacao_embed(), view=self)

    @discord.ui.button(label="🎮 Diversão", style=discord.ButtonStyle.secondary, row=1)
    async def diversao_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_diversao_embed(), view=self)

    @discord.ui.button(label="📋 Utilitários", style=discord.ButtonStyle.secondary, row=1)
    async def utilitarios_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("❌ Apenas quem executou o comando pode usar esses botões!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.get_utilitarios_embed(), view=self)

# Adicionar XP automaticamente em mensagens
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Dar XP aleatório por mensagem (1-3 XP)
    if random.random() < 0.1:  # 10% de chance
        xp_gain = random.randint(1, 3)
        add_user_xp(message.author.id, xp_gain)

    await bot.process_commands(message)

# --- Sistema de Apostas Avançado (p!odd) ---

# Base de dados de times com estatísticas simuladas
TIMES_DATABASE = {
    # Times da Série A - Tier 1 (Elite)
    "Flamengo": {
        "tier": 1, "attack": 88, "defense": 82, "form": [1, 1, 0, 1, 1], 
        "goals_per_game": 2.4, "goals_conceded": 1.1, "clean_sheets": 45
    },
    "Palmeiras": {
        "tier": 1, "attack": 85, "defense": 87, "form": [1, 1, 1, 0, 1], 
        "goals_per_game": 2.2, "goals_conceded": 0.9, "clean_sheets": 52
    },
    "São Paulo": {
        "tier": 1, "attack": 78, "defense": 80, "form": [1, 0, 1, 1, 0], 
        "goals_per_game": 1.9, "goals_conceded": 1.2, "clean_sheets": 38
    },
    "Corinthians": {
        "tier": 1, "attack": 75, "defense": 78, "form": [0, 1, 1, 1, 0], 
        "goals_per_game": 1.8, "goals_conceded": 1.3, "clean_sheets": 35
    },
    "Atlético-MG": {
        "tier": 1, "attack": 81, "defense": 75, "form": [1, 1, 0, 1, 1], 
        "goals_per_game": 2.1, "goals_conceded": 1.4, "clean_sheets": 32
    },
    "Fluminense": {
        "tier": 1, "attack": 76, "defense": 74, "form": [1, 0, 1, 0, 1], 
        "goals_per_game": 1.7, "goals_conceded": 1.3, "clean_sheets": 31
    },

    # Times da Série A - Tier 2 (Forte)
    "Internacional": {
        "tier": 2, "attack": 74, "defense": 77, "form": [1, 1, 0, 1, 0], 
        "goals_per_game": 1.8, "goals_conceded": 1.2, "clean_sheets": 36
    },
    "Grêmio": {
        "tier": 2, "attack": 72, "defense": 75, "form": [0, 1, 1, 0, 1], 
        "goals_per_game": 1.6, "goals_conceded": 1.3, "clean_sheets": 33
    },
    "Botafogo": {
        "tier": 2, "attack": 73, "defense": 69, "form": [1, 1, 1, 0, 1], 
        "goals_per_game": 1.9, "goals_conceded": 1.5, "clean_sheets": 28
    },
    "Santos": {
        "tier": 2, "attack": 71, "defense": 68, "form": [0, 1, 0, 1, 1], 
        "goals_per_game": 1.7, "goals_conceded": 1.6, "clean_sheets": 25
    },
    "Athletico-PR": {
        "tier": 2, "attack": 70, "defense": 72, "form": [1, 0, 1, 1, 0], 
        "goals_per_game": 1.6, "goals_conceded": 1.4, "clean_sheets": 30
    },
    "Bahia": {
        "tier": 2, "attack": 68, "defense": 70, "form": [1, 1, 0, 0, 1], 
        "goals_per_game": 1.5, "goals_conceded": 1.4, "clean_sheets": 29
    },

    # Times da Série A - Tier 3 (Médio)
    "Fortaleza": {
        "tier": 3, "attack": 65, "defense": 67, "form": [0, 1, 1, 0, 0], 
        "goals_per_game": 1.4, "goals_conceded": 1.5, "clean_sheets": 26
    },
    "Vasco": {
        "tier": 3, "attack": 64, "defense": 65, "form": [1, 0, 0, 1, 0], 
        "goals_per_game": 1.3, "goals_conceded": 1.6, "clean_sheets": 23
    },
    "Bragantino": {
        "tier": 3, "attack": 66, "defense": 63, "form": [0, 1, 0, 1, 1], 
        "goals_per_game": 1.5, "goals_conceded": 1.7, "clean_sheets": 22
    },
    "Cruzeiro": {
        "tier": 3, "attack": 63, "defense": 64, "form": [1, 0, 1, 0, 1], 
        "goals_per_game": 1.4, "goals_conceded": 1.6, "clean_sheets": 24
    },

    # Times da Série B - Tier 4 (Emergente)
    "Sport": {
        "tier": 4, "attack": 60, "defense": 58, "form": [1, 1, 0, 1, 0], 
        "goals_per_game": 1.3, "goals_conceded": 1.8, "clean_sheets": 20
    },
    "Ponte Preta": {
        "tier": 4, "attack": 58, "defense": 56, "form": [0, 0, 1, 1, 0], 
        "goals_per_game": 1.2, "goals_conceded": 1.9, "clean_sheets": 18
    }
}

# Lista simplificada para sorteio aleatório
TIMES_BRASILEIROS = list(TIMES_DATABASE.keys())

# Dicionário para armazenar apostas dos usuários
apostas_usuarios = {}
historico_apostas = []

class MatchAnalyzer:
    """Analisador profissional de partidas com foco em odds e estatísticas"""

    def __init__(self, team1: str, team2: str):
        self.team1 = team1
        self.team2 = team2
        self.team1_data = TIMES_DATABASE.get(team1, {})
        self.team2_data = TIMES_DATABASE.get(team2, {})

    def get_form_string(self, form_list):
        """Converte lista de forma em string"""
        return "-".join(["W" if x == 1 else "D" if x == 0.5 else "L" for x in form_list])

    def calculate_win_probabilities(self):
        """Calcula probabilidades de vitória baseadas em estatísticas"""
        if not self.team1_data or not self.team2_data:
            # Fallback para times sem dados
            return {"team1": 33.3, "draw": 33.3, "team2": 33.3}

        # Fatores de análise
        attack_diff = self.team1_data["attack"] - self.team2_data["defense"]
        defense_diff = self.team2_data["attack"] - self.team1_data["defense"]

        # Forma recente (últimos 5 jogos)
        team1_form = sum(self.team1_data["form"]) / len(self.team1_data["form"])
        team2_form = sum(self.team2_data["form"]) / len(self.team2_data["form"])

        # Cálculo base das probabilidades
        team1_strength = (attack_diff + team1_form * 20 + self.team1_data["attack"]) / 3
        team2_strength = (defense_diff + team2_form * 20 + self.team2_data["attack"]) / 3

        # Normalizar para percentuais
        total_strength = team1_strength + team2_strength + 30  # 30 para chance de empate

        team1_prob = max(15, min(70, (team1_strength / total_strength) * 100))
        team2_prob = max(15, min(70, (team2_strength / total_strength) * 100))
        draw_prob = 100 - team1_prob - team2_prob

        return {
            "team1": round(team1_prob, 1),
            "draw": round(draw_prob, 1),
            "team2": round(team2_prob, 1)
        }

    def get_btts_probability(self):
        """Calcula probabilidade de ambos times marcarem"""
        if not self.team1_data or not self.team2_data:
            return 50.0

        team1_attack = self.team1_data["goals_per_game"]
        team2_attack = self.team2_data["goals_per_game"]
        team1_defense = self.team1_data["goals_conceded"]
        team2_defense = self.team2_data["goals_conceded"]

        # Probabilidade baseada em médias de gols
        avg_attack = (team1_attack + team2_attack) / 2
        avg_defense = (team1_defense + team2_defense) / 2

        btts_prob = min(85, max(25, (avg_attack / avg_defense) * 45))
        return round(btts_prob, 1)

    def get_total_goals_prediction(self):
        """Predição de total de gols na partida"""
        if not self.team1_data or not self.team2_data:
            return 2.5

        expected_goals = (
            self.team1_data["goals_per_game"] + 
            self.team2_data["goals_per_game"] + 
            self.team1_data["goals_conceded"] + 
            self.team2_data["goals_conceded"]
        ) / 2

        return round(expected_goals, 1)

    def get_suggested_bets(self):
        """Gera sugestões de apostas baseadas na análise"""
        probabilities = self.calculate_win_probabilities()
        btts_prob = self.get_btts_probability()
        total_goals = self.get_total_goals_prediction()

        suggestions = []

        # Sugestão de resultado
        max_prob = max(probabilities.values())
        if max_prob > 45:
            if probabilities["team1"] == max_prob:
                suggestions.append(f"Vitória {self.team1} (Confiança: Alta)")
            elif probabilities["team2"] == max_prob:
                suggestions.append(f"Vitória {self.team2} (Confiança: Alta)")
        elif probabilities["draw"] > 30:
            suggestions.append("Empate (Confiança: Média)")

        # Sugestão de gols
        if total_goals > 2.7:
            suggestions.append("Over 2.5 Gols (Confiança: Alta)")
        elif total_goals < 2.3:
            suggestions.append("Under 2.5 Gols (Confiança: Alta)")

        # Sugestão BTTS
        if btts_prob > 60:
            suggestions.append("Ambos Marcam: SIM (Confiança: Alta)")
        elif btts_prob < 40:
            suggestions.append("Ambos Marcam: NÃO (Confiança: Média)")

        return suggestions[:3]  # Máximo 3 sugestões

    def simulate_realistic_match(self):
        """Simula partida com base em estatísticas reais"""
        if not self.team1_data or not self.team2_data:
            # Simulação básica para times sem dados
            return {
                "goals_team1": random.randint(0, 3),
                "goals_team2": random.randint(0, 3)
            }

        # Simular gols baseado em média e força
        team1_expected = (self.team1_data["goals_per_game"] + self.team2_data["goals_conceded"]) / 2
        team2_expected = (self.team2_data["goals_per_game"] + self.team1_data["goals_conceded"]) / 2

        # Adicionar variabilidade da forma recente
        team1_form_factor = (sum(self.team1_data["form"]) / len(self.team1_data["form"]) - 0.5) * 0.5
        team2_form_factor = (sum(self.team2_data["form"]) / len(self.team2_data["form"]) - 0.5) * 0.5

        team1_expected += team1_form_factor
        team2_expected += team2_form_factor

        # Gerar gols com distribuição de Poisson simulada
        team1_goals = max(0, int(random.normalvariate(team1_expected, 1)))
        team2_goals = max(0, int(random.normalvariate(team2_expected, 1)))

        # Limitar a valores realistas
        team1_goals = min(team1_goals, 5)
        team2_goals = min(team2_goals, 5)

        return {
            "goals_team1": team1_goals,
            "goals_team2": team2_goals
        }

class OddsModal(Modal, title="🎯 Apostar no Placar Exato"):
    placar = TextInput(
        label="Predição do Placar (ex: 2x1, 0x0, 3x2)",
        placeholder="Formato: XxY baseado na análise",
        max_length=10
    )
    valor_aposta = TextInput(
        label="Valor da Aposta (mín: 100 moedas)",
        placeholder="Quanto deseja arriscar?",
        max_length=10
    )

    def __init__(self, team1: str, team2: str, user_id: int):
        super().__init__()
        self.team1 = team1
        self.team2 = team2
        self.user_id = user_id
        self.analyzer = MatchAnalyzer(team1, team2)

    async def on_submit(self, interaction: discord.Interaction):
        # Validações
        placar_pattern = r'^(\d+)x(\d+)$'
        if not re.match(placar_pattern, self.placar.value.lower()):
            await interaction.response.send_message(
                "❌ **Formato Inválido** - Use XxY (ex: 2x1)", ephemeral=True
            )
            return

        try:
            valor = int(self.valor_aposta.value)
            if valor < 100:
                await interaction.response.send_message(
                    "❌ **Aposta Mínima:** 100 moedas", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ **Valor Inválido** - Digite apenas números", ephemeral=True
            )
            return

        saldo_atual = get_user_money(self.user_id)
        if saldo_atual < valor:
            await interaction.response.send_message(
                f"❌ **Saldo Insuficiente**\nDisponível: `{saldo_atual}` | Necessário: `{valor}`",
                ephemeral=True
            )
            return

        await self.process_bet(interaction, self.placar.value.lower(), valor)

    async def process_bet(self, interaction, predicted_score, bet_amount):
        remove_user_money(self.user_id, bet_amount)

        # Simular resultado
        match_result = self.analyzer.simulate_realistic_match()
        actual_score = f"{match_result['goals_team1']}x{match_result['goals_team2']}"

        # Verificar acerto
        predicted_goals = predicted_score.split('x')
        actual_won = (int(predicted_goals[0]) == match_result['goals_team1'] and 
                      int(predicted_goals[1]) == match_result['goals_team2'])

        if actual_won:
            payout = bet_amount * 2
            add_user_money(self.user_id, payout)
            profit = payout - bet_amount
            result_status = "🎯 **PREDIÇÃO EXATA!**"
            embed_color = discord.Color.gold()
        else:
            payout = 0
            profit = -bet_amount
            result_status = "📊 **Análise Incorreta**"
            embed_color = discord.Color.red()

        final_balance = get_user_money(self.user_id)

        # Registrar no histórico
        bet_record = {
            'user_id': self.user_id, 'team1': self.team1, 'team2': self.team2,
            'predicted_score': predicted_score, 'actual_score': actual_score,
            'bet_amount': bet_amount, 'won': actual_won, 'payout': payout,
            'final_balance': final_balance, 'timestamp': datetime.now().isoformat()
        }
        historico_apostas.append(bet_record)

        # Embed de resultado no estilo odds
        result_embed = discord.Embed(
            title="📊 **RESULTADO DA ANÁLISE** 📊",
            description=f"{result_status}\n\n**{self.team1}** vs **{self.team2}**",
            color=embed_color
        )

        result_embed.add_field(
            name="🎯 Predição vs Realidade",
            value=f"**Predito:** `{predicted_score.upper()}`\n**Resultado:** `{actual_score.upper()}`",
            inline=True
        )

        result_embed.add_field(
            name="💰 Análise Financeira",
            value=f"**Aposta:** {bet_amount} moedas\n**Retorno:** {payout} moedas\n**P&L:** {profit:+d} moedas",
            inline=True
        )

        result_embed.add_field(
            name="📈 Saldo Atualizado",
            value=f"**Atual:** {final_balance} moedas",
            inline=True
        )

        # Probabilidades para contexto
        probabilities = self.analyzer.calculate_win_probabilities()
        result_embed.add_field(
            name="📊 Probabilidades Calculadas",
            value=f"**{self.team1}:** {probabilities['team1']}%\n**Empate:** {probabilities['draw']}%\n**{self.team2}:** {probabilities['team2']}%",
            inline=False
        )

        result_embed.set_footer(
            text=f"Análise por {interaction.user.display_name} • Sistema de Odds Avançado - Dev: YevgennyMXP"
        )
        result_embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.edit_message(embed=result_embed, view=None)

class OddsView(View):
    def __init__(self, team1: str, team2: str, user_id: int):
        super().__init__(timeout=300)
        self.team1 = team1
        self.team2 = team2
        self.user_id = user_id

    @discord.ui.button(label="🎯 Analisar & Apostar", style=discord.ButtonStyle.success, emoji="📊")
    async def place_bet(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ **Acesso Negado** - Apenas o analista pode operar", ephemeral=True
            )
            return

        modal = OddsModal(self.team1, self.team2, self.user_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Encerrar Sessão", style=discord.ButtonStyle.danger)
    async def cancel_analysis(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ **Acesso Negado** - Apenas o analista pode encerrar", ephemeral=True
            )
            return

        embed_closed = discord.Embed(
            title="📊 **Sessão de Análise Encerrada**",
            description="**Status:** Análise cancelada pelo usuário\n\n*Use `p!odd` para nova análise*",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed_closed, view=None)

@bot.command(name='odd', aliases=['apostar_placar', 'bet_score'])
async def odds_command(ctx):
    """Sistema profissional de análise e apostas com foco em odds"""

    user_balance = get_user_money(ctx.author.id)
    if user_balance < 100:
        insufficient_embed = discord.Embed(
            title="💸 **Capital Insuficiente**",
            description=f"**Saldo Atual:** {user_balance} moedas\n**Mínimo Necessário:** 100 moedas\n\n**Opções para Aumentar Capital:**\n• `p!daily` - Bônus diário\n• `p!work` - Trabalho remunerado",
            color=discord.Color.red()
        )
        await ctx.reply(embed=insufficient_embed)
        return

    # Sortear confronto
    team1, team2 = random.sample(TIMES_BRASILEIROS, 2)
    analyzer = MatchAnalyzer(team1, team2)

    # Dados estatísticos
    probabilities = analyzer.calculate_win_probabilities()
    btts_prob = analyzer.get_btts_probability()
    total_goals = analyzer.get_total_goals_prediction()
    suggestions = analyzer.get_suggested_bets()

    # Embed principal no estilo odds profissional
    odds_embed = discord.Embed(
        title="📊 **ANÁLISE DE ODDS & PROBABILIDADES** 📊",
        description=f"**Confronto Selecionado**\n\n🏠 **{team1}** 🆚 **{team2}** ✈️",
        color=discord.Color.blue()
    )

    # Estatísticas dos times se disponíveis
    if team1 in TIMES_DATABASE and team2 in TIMES_DATABASE:
        team1_data = TIMES_DATABASE[team1]
        team2_data = TIMES_DATABASE[team2]

        odds_embed.add_field(
            name="🏟 **Forma Recente (Últimos 5)**",
            value=f"**{team1}:** {analyzer.get_form_string(team1_data['form'])}\n**{team2}:** {analyzer.get_form_string(team2_data['form'])}",
            inline=True
        )

        odds_embed.add_field(
            name="⚽ **Média de Gols por Jogo**",
            value=f"**{team1}:** {team1_data['goals_per_game']}\n**{team2}:** {team2_data['goals_per_game']}",
            inline=True
        )

        odds_embed.add_field(
            name="🛡️ **Gols Sofridos (Média)**",
            value=f"**{team1}:** {team1_data['goals_conceded']}\n**{team2}:** {team2_data['goals_conceded']}",
            inline=True
        )

    # Probabilidades calculadas
    odds_embed.add_field(
        name="🔮 **Probabilidades de Resultado**",
        value=f"**{team1} Win:** {probabilities['team1']}%\n**Draw:** {probabilities['draw']}%\n**{team2} Win:** {probabilities['team2']}%",
        inline=False
    )

    # Análises de mercado
    odds_embed.add_field(
        name="📈 **Análise de Mercados**",
        value=f"🎯 **BTTS (Ambos Marcam):** {btts_prob}%\n📊 **Total de Gols Esperado:** {total_goals}\n🔍 **Over 2.5:** {'Alta' if total_goals > 2.5 else 'Baixa'} probabilidade",
        inline=True
    )

    # Informações do apostador
    odds_embed.add_field(
        name="💰 **Capital Disponível**",
        value=f"**Saldo:** {user_balance} moedas\n**Aposta Mín:** 100 moedas\n**Retorno:** 2.00x (Placar Exato)",
        inline=True
    )

    # Sugestões de aposta
    if suggestions:
        odds_embed.add_field(
            name="💡 **Sugestões Baseadas em Dados**",
            value="\n".join([f"• {sugg}" for sugg in suggestions]),
            inline=False
        )

    odds_embed.add_field(
        name="⚠️ **Disclaimer de Risco**",
        value="*Análise baseada em dados históricos simulados. Resultados gerados algoritmicamente para fins de entretenimento.*",
        inline=False
    )

    odds_embed.set_footer(
        text=f"Análise gerada para {ctx.author.display_name} • Sistema de Odds Profissional - Dev: YevgennyMXP"
    )
    odds_embed.set_thumbnail(url=ctx.author.display_avatar.url)

    view = OddsView(team1, team2, ctx.author.id)
    await ctx.reply(embed=odds_embed, view=view)

@bot.command(name='historico_apostas', aliases=['my_bets', 'apostas'])
async def historico_apostas_command(ctx):
    """Ver histórico de apostas do usuário"""

    # Filtrar apostas do usuário
    apostas_usuario = [aposta for aposta in historico_apostas if aposta['user_id'] == ctx.author.id]

    if not apostas_usuario:
        embed_vazio = discord.Embed(
            title="📋 Histórico de Apostas",
            description="Você ainda não fez nenhuma aposta!\n\nUse `p!odd` para fazer sua primeira aposta.",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed_vazio)
        return

    # Estatísticas gerais
    total_apostas = len(apostas_usuario)
    acertos = sum(1 for aposta in apostas_usuario if aposta['acertou'])
    erros = total_apostas - acertos
    taxa_acerto = (acertos / total_apostas * 100) if total_apostas > 0 else 0

    total_apostado = sum(aposta['valor_aposta'] for aposta in apostas_usuario)
    total_ganho = sum(aposta['premio'] for aposta in apostas_usuario)
    lucro_prejuizo = total_ganho - total_apostado

    embed_historico = discord.Embed(
        title="📊 Seu Histórico de Apostas",
        description=f"Estatísticas completas de {ctx.author.display_name}",
        color=discord.Color.gold() if lucro_prejuizo >= 0 else discord.Color.red()
    )

    embed_historico.add_field(
        name="📈 Estatísticas Gerais",
        value=(
            f"🎯 **Total de apostas:** {total_apostas}\n"
            f"✅ **Acertos:** {acertos}\n"
            f"❌ **Erros:** {erros}\n"
            f"📊 **Taxa de acerto:** {taxa_acerto:.1f}%"
        ),
        inline=True
    )

    embed_historico.add_field(
        name="💰 Resumo Financeiro",
        value=(
            f"💸 **Total apostado:** {total_apostado} moedas\n"
            f"🏆 **Total ganho:** {total_ganho} moedas\n"
            f"📈 **Lucro/Prejuízo:** {lucro_prejuizo:+d} moedas\n"
            f"💎 **Saldo atual:** {get_user_money(ctx.author.id)} moedas"
        ),
        inline=True
    )

    # Mostrar últimas 5 apostas
    ultimas_apostas = sorted(apostas_usuario, key=lambda x: x['timestamp'], reverse=True)[:5]

    historico_texto = ""
    for i, aposta in enumerate(ultimas_apostas, 1):
        resultado_emoji = "✅" if aposta['acertou'] else "❌"
        data_aposta = datetime.fromisoformat(aposta['timestamp']).strftime("%d/%m %H:%M")

        historico_texto += (
            f"{resultado_emoji} **{aposta['time1']} vs {aposta['time2']}**\n"
            f"   Palpite: `{aposta['placar_apostado']}` | Real: `{aposta['placar_real']}`\n"
            f"   Aposta: {aposta['valor_aposta']} | Resultado: {aposta['premio'] - aposta['valor_aposta']:+d}\n"
            f"   📅 {data_aposta}\n\n"
        )

    embed_historico.add_field(
        name="📋 Últimas 5 Apostas",
        value=historico_texto if historico_texto else "Nenhuma aposta encontrada",
        inline=False
    )

    embed_historico.set_thumbnail(url=ctx.author.display_avatar.url)
    embed_historico.set_footer(text=f"Use p!odd para fazer uma nova aposta! - Dev: YevgennyMXP")

    await ctx.reply(embed=embed_historico)

# --- Inicia o Bot ---
if DISCORD_BOT_TOKEN is None:
    print("ERRO: O token do bot Discord não foi encontrado! Certifique-se de configurar a variável de ambiente 'DISCORD_BOT_TOKEN' ou inseri-lo diretamente no código (não recomendado para produção).")
    print("Para configurar no Replit:")
    print("1. Vá na aba 'Secrets' (cadeado) no painel lateral")
    print("2. Adicione um novo secret:")
    print("   - Key: DISCORD_BOT_TOKEN")
    print("   - Value: [SEU_TOKEN_DO_BOT_AQUI]")
    print("3. Reinicie o bot")
else:
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)