import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import csv
import asyncio

load_dotenv()

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = commands.Bot(command_prefix="/", intents=intents)

study_channel_id = 1040912827923316760
report_channel_id = 1040912827923316760
user_entry_times = {}


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
                await channel.send(embed=embed)

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
            with open("study_times.csv", "r", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    entry_time_csv = datetime.fromisoformat(row[2])
                    exit_time_csv = datetime.fromisoformat(row[3])
                    if entry_time_csv.date() == today:
                        total_study_time += exit_time_csv - entry_time_csv

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
                        name="이번 세션 스터디 시간",
                        value=str(study_duration).split(".")[0],
                        inline=False,
                    )
                    embed.add_field(
                        name="오늘의 총 스터디 시간",
                        value=total_study_time_str,
                        inline=False,
                    )
                    await channel.send(embed=embed)

            with open("study_times.csv", "a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        member.id,
                        member.display_name,
                        entry_time,
                        datetime.now(),
                        study_duration,
                    ]
                )


@client.tree.command(name="공부시간", description="오늘 공부한 시간을 출력합니다.")
async def study_time(interaction: discord.Interaction):
    today = datetime.now().date()
    total_study_time = timedelta()
    with open("study_times.csv", "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            entry_time = datetime.fromisoformat(row[2])
            exit_time = datetime.fromisoformat(row[3])
            if entry_time.date() == today:
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
    with open("study_times.csv", "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
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


async def daily_report():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_run - now).total_seconds())

        with open("study_times.csv", "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            today = datetime.now().date()
            total_study_time = timedelta()
            for row in reader:
                entry_time = datetime.fromisoformat(row[2])
                exit_time = datetime.fromisoformat(row[3])
                if entry_time.date() == today:
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
    client.loop.create_task(daily_report())


client.run(TOKEN)
