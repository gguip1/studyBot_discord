import os
import sqlite3
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

load_dotenv()

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = commands.Bot(command_prefix="/", intents=intents)

study_channel_id = None
report_channel_id = None
user_entry_times = {}
user_message_ids = {}

# SQLite 데이터베이스 초기화
conn = sqlite3.connect("study_times.db")
c = conn.cursor()
c.execute(
    """
    CREATE TABLE IF NOT EXISTS study_times (
        user_id TEXT,
        user_name TEXT,
        entry_time TEXT,
        exit_time TEXT,
        study_duration TEXT
    )
    """
)
conn.commit()


@client.tree.command(name="채널설정", description="스터디 채널을 설정합니다.")
async def setChannelID(interaction: discord.Interaction, channel_id: int):
    for guild in client.guilds:
        channel = guild.get_channel(channel_id)
        if channel:
            global study_channel_id
            study_channel_id = channel_id
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="채널 설정",
                    description=f"스터디 채널이 {channel.name}으로 설정되었습니다.",
                    color=discord.Color.green(),
                )
            )
            print(study_channel_id)
            return
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="채널 설정 오류",
                    description="해당 채널이 존재하지 않습니다.",
                    color=discord.Color.red(),
                )
            )


@client.tree.command(
    name="보고채널설정", description="보고서를 보낼 채널을 설정합니다."
)
async def setReportChannelID(interaction: discord.Interaction, channel_id: int):
    for guild in client.guilds:
        channel = guild.get_channel(channel_id)
        if channel:
            global report_channel_id
            report_channel_id = channel_id
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="보고 채널 설정",
                    description=f"보고 채널이 {channel.name}으로 설정되었습니다.",
                    color=discord.Color.green(),
                )
            )
            print(report_channel_id)
            return
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="보고 채널 설정 오류",
                    description="해당 채널이 존재하지 않습니다.",
                    color=discord.Color.red(),
                )
            )


@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:  # 봇인 경우 무시
        return

    # 화면 공유 상태 변경 시 무시
    if before.channel == after.channel:
        return

    # 스터디 채널에 입장한 경우 (다른 채널에서 이동 포함)
    if after.channel is not None and after.channel.id == study_channel_id:
        user_entry_times[member.id] = datetime.now()
        if report_channel_id:
            channel = client.get_channel(report_channel_id)
            if channel:
                embed = discord.Embed(
                    title="스터디 시작 📚",
                    description=f"{member.display_name}님이 스터디 채널에 입장하셨습니다. 스터디를 시작합니다.",
                    color=discord.Color.blue(),
                )
                embed.add_field(
                    name="현재 공부 시간 ⏰", value="00:00:00", inline=False
                )
                embed.set_thumbnail(url=member.avatar.url)
                message = await channel.send(embed=embed)
                user_message_ids[member.id] = message.id
                update_study_time.start(member.id, message)

    # 스터디 채널에서 나간 경우 (다른 채널로 이동 포함)
    elif (
        before.channel is not None
        and before.channel.id == study_channel_id
        and (after.channel is None or after.channel.id != study_channel_id)
    ):
        entry_time = user_entry_times.pop(member.id, None)
        if entry_time:
            study_duration = datetime.now() - entry_time
            total_study_time = timedelta()
            today = datetime.now().date()

            # 오늘의 총 스터디 시간 계산
            c.execute(
                "SELECT entry_time, exit_time FROM study_times WHERE DATE(entry_time) = ?",
                (today,),
            )
            rows = c.fetchall()
            for row in rows:
                entry_time_db = datetime.fromisoformat(row[0])
                exit_time_db = datetime.fromisoformat(row[1])
                total_study_time += exit_time_db - entry_time_db

            total_study_time += study_duration  # 현재 세션 시간 추가

            # timedelta를 HH:MM:SS 형식으로 변환
            total_study_time_str = str(total_study_time).split(".")[0]

            if report_channel_id:
                channel = client.get_channel(report_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="스터디 종료 🛑",
                        description=f"{member.display_name}님이 스터디 채널에서 나가셨습니다. 스터디를 종료합니다.",
                        color=discord.Color.orange(),
                    )
                    embed.add_field(
                        name="이번 세션 스터디 시간 ⏰",
                        value=str(study_duration).split(".")[0],
                        inline=False,
                    )
                    embed.add_field(
                        name="오늘의 총 스터디 시간 📅",
                        value=total_study_time_str,
                        inline=False,
                    )
                    embed.set_thumbnail(url=member.avatar.url)
                    await channel.send(embed=embed)

            # SQLite에 데이터 저장
            c.execute(
                "INSERT INTO study_times (user_id, user_name, entry_time, exit_time, study_duration) VALUES (?, ?, ?, ?, ?)",
                (
                    member.id,
                    member.display_name,
                    entry_time.isoformat(),
                    datetime.now().isoformat(),
                    str(study_duration),
                ),
            )
            conn.commit()
            update_study_time.stop()


@tasks.loop(seconds=1)
async def update_study_time(user_id, message):
    try:
        if user_id in user_entry_times:
            entry_time = user_entry_times[user_id]
            study_duration = datetime.now() - entry_time
            user = await client.fetch_user(user_id)
            embed = message.embeds[0]
            embed.set_field_at(
                0,
                name="현재 공부 시간 ⏰",
                value=str(study_duration).split(".")[0],
                inline=False,
            )
            await message.edit(embed=embed)
    except Exception as e:
        print(f"Error updating study time for user {user_id}: {e}")


@client.tree.command(name="공부시간", description="오늘 공부한 시간을 출력합니다.")
async def study_time(interaction: discord.Interaction):
    today = datetime.now().date()
    total_study_time = timedelta()
    c.execute(
        "SELECT entry_time, exit_time FROM study_times WHERE DATE(entry_time) = ?",
        (today,),
    )
    rows = c.fetchall()
    for row in rows:
        entry_time = datetime.fromisoformat(row[0])
        exit_time = datetime.fromisoformat(row[1])
        total_study_time += exit_time - entry_time

    # timedelta를 HH:MM:SS 형식으로 변환
    total_study_time_str = str(total_study_time).split(".")[0]

    await interaction.response.send_message(
        embed=discord.Embed(
            title="오늘의 총 스터디 시간 ⏰",
            description=total_study_time_str,
            color=discord.Color.purple(),
        )
    )


@client.tree.command(
    name="공부시간탑10", description="공부 시간 상위 10명을 출력합니다."
)
async def study_time_top10(interaction: discord.Interaction):
    user_study_times = {}
    c.execute("SELECT user_id, user_name, entry_time, exit_time FROM study_times")
    rows = c.fetchall()
    for row in rows:
        user_id = row[0]
        user_name = row[1]
        entry_time = datetime.fromisoformat(row[2])
        exit_time = datetime.fromisoformat(row[3])
        study_duration = exit_time - entry_time
        if user_id in user_study_times:
            user_study_times[user_id]["total_time"] += study_duration
        else:
            user_study_times[user_id] = {
                "name": user_name,
                "total_time": study_duration,
            }

    # 상위 10명 정렬
    top10 = sorted(
        user_study_times.items(), key=lambda x: x[1]["total_time"], reverse=True
    )[:10]

    embed = discord.Embed(title="공부 시간 상위 10명 🏆", color=discord.Color.gold())

    for i, (user_id, data) in enumerate(top10, start=1):
        total_time_str = str(data["total_time"]).split(".")[0]
        embed.add_field(name=f"{i}. {data['name']}", value=total_time_str, inline=False)

    await interaction.response.send_message(embed=embed)


@tasks.loop(hours=24)
async def daily_record():
    await client.wait_until_ready()
    now = datetime.now()
    today = now.date()
    for guild in client.guilds:
        for member in guild.members:
            if member.id in user_entry_times:
                entry_time = user_entry_times[member.id]
                study_duration = now - entry_time
                c.execute(
                    "INSERT INTO study_times (user_id, user_name, entry_time, exit_time, study_duration) VALUES (?, ?, ?, ?, ?)",
                    (
                        member.id,
                        member.display_name,
                        entry_time.isoformat(),
                        now.isoformat(),
                        str(study_duration),
                    ),
                )
                conn.commit()
                user_entry_times[member.id] = now  # Reset entry time to now


async def daily_report():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_run - now).total_seconds())

        today = datetime.now().date()
        total_study_time = timedelta()
        c.execute(
            "SELECT entry_time, exit_time FROM study_times WHERE DATE(entry_time) = ?",
            (today,),
        )
        rows = c.fetchall()
        for row in rows:
            entry_time = datetime.fromisoformat(row[0])
            exit_time = datetime.fromisoformat(row[1])
            total_study_time += exit_time - entry_time

        # timedelta를 HH:MM:SS 형식으로 변환
        total_study_time_str = str(total_study_time).split(".")[0]

        if report_channel_id:
            channel = client.get_channel(report_channel_id)
            if channel:
                embed = discord.Embed(
                    title="오늘의 총 스터디 시간 ⏰",
                    description=total_study_time_str,
                    color=discord.Color.purple(),
                )
                await channel.send(embed=embed)


@client.event
async def on_ready():
    await client.tree.sync()  # 명령어 동기화
    daily_record.start()  # 매일 00:00에 기록 시작
    client.loop.create_task(daily_report())


client.run(TOKEN)
