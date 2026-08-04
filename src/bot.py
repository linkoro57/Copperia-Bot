import asyncio
import logging
import os
import re
import time

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

from src.config import (
    CHANNEL_IDS,
    DEVELOPER_NAME,
    GUILD_ID,
    TEMP_BAN_DURATION_SECONDS,
    TICKETS_CATEGORY_ID,
    VOICE_CHANNEL_ID,
)
from src.storage import read_state, write_state


logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
state = read_state()


def save_state():
    write_state(state)


async def resolve_channel(guild: discord.Guild, channel_id: int):
    channel = guild.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await guild.fetch_channel(channel_id)
    except discord.DiscordException:
        logging.warning("Salon introuvable ou inaccessible: %s", channel_id)
        return None


def get_avatar_url(user: discord.abc.User) -> str:
    avatar = user.display_avatar
    if avatar.is_animated():
        return avatar.replace(format="gif", size=512).url
    return avatar.replace(format="png", size=512).url


def build_regulation_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Reglement du serveur Copperia Externat",
        description=(
            "Merci de lire et respecter les regles ci-dessous pour garder un serveur sain, "
            "propre et agreable pour tout le monde."
        ),
        color=0xB87333,
    )
    embed.add_field(
        name="1. Respect",
        value=(
            "Respecte tous les membres. Les insultes, provocations, harcelement, "
            "discriminations et comportements toxiques sont interdits."
        ),
        inline=False,
    )
    embed.add_field(
        name="2. Contenu autorise",
        value="Pas de spam, flood, pub sauvage, scam, contenu choquant, NSFW, dangereux ou illegal.",
        inline=False,
    )
    embed.add_field(
        name="3. Bonne conduite",
        value="Reste poli, utilise les bons salons, evite les conflits publics et suis les indications du staff.",
        inline=False,
    )
    embed.add_field(
        name="4. Comptes et securite",
        value="Protege ton compte. Toute tentative d'arnaque, de piratage ou d'usurpation sera sanctionnee.",
        inline=False,
    )
    embed.add_field(
        name="5. Sanctions",
        value="Selon la gravite : avertissement, mute, kick, bannissement temporaire ou definitif.",
        inline=False,
    )
    embed.set_footer(text=f"Copperia Bot - Developpe par {DEVELOPER_NAME}")
    return embed


def build_welcome_embed(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"Salut {member.display_name}",
        description="Bienvenue dans le serveur Copperia Externat !",
        color=0xB87333,
    )
    embed.set_thumbnail(url=get_avatar_url(member))
    return embed


def build_anti_scam_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Ne pas ecrire",
        description=(
            "Ce salon sert a attraper les comptes pirates qui diffusent des arnaques.\n"
            "Ecrire ici entrainera un bannissement temporaire d'une semaine, sans appel possible."
        ),
        color=0xAA0000,
    )
    return embed


def build_ticket_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Ouvrir un ticket",
        description=(
            "Si tu as besoin d'aide, de support, que tu souhaites faire du commerce "
            "ou une alliance, clique ci-dessous."
        ),
        color=0xB87333,
    )
    return embed


def build_ticket_embed(ticket_type: str) -> discord.Embed:
    embed = discord.Embed(
        title="Bienvenue sur ton ticket",
        description="Un membre du pays viendra bientot te voir.",
        color=0xB87333,
    )
    embed.add_field(name="Categorie", value=ticket_type, inline=False)
    return embed


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Besoin d'aide", value="Besoin d'aide"),
            discord.SelectOption(label="Alliance", value="Alliance"),
            discord.SelectOption(label="Commerce", value="Commerce"),
        ]
        super().__init__(
            placeholder="Choisis le type de ticket",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.values[0])


class TicketTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TicketTypeSelect())


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ouvrir un ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:open",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        del button
        await interaction.response.send_message(
            "Choisis la categorie de ton ticket.",
            view=TicketTypeView(),
            ephemeral=True,
        )


class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Prendre en charge",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim",
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        del button
        ticket_data = state["tickets"]["channels"].get(str(interaction.channel_id))
        if not ticket_data:
            await interaction.response.send_message("Ticket introuvable.", ephemeral=True)
            return

        if interaction.user.id == ticket_data["owner_id"]:
            await interaction.response.send_message(
                "Tu ne peux pas prendre en charge ton propre ticket.",
                ephemeral=True,
            )
            return

        ticket_data["claimed_by"] = interaction.user.id
        save_state()
        await interaction.response.send_message(
            f"Ce ticket a ete pris en charge par {interaction.user.mention}"
        )

    @discord.ui.button(
        label="Supprimer",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:delete",
    )
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        del button
        ticket_data = state["tickets"]["channels"].get(str(interaction.channel_id))
        if not ticket_data:
            await interaction.response.send_message("Ticket introuvable.", ephemeral=True)
            return

        if ticket_data.get("claimed_by") != interaction.user.id:
            await interaction.response.send_message(
                "Seule la personne qui a pris en charge le ticket peut le supprimer.",
                ephemeral=True,
            )
            return

        category = await resolve_channel(interaction.guild, TICKETS_CATEGORY_ID)
        if isinstance(category, discord.CategoryChannel):
            try:
                target = interaction.guild.get_member(ticket_data["owner_id"])
                if target is not None:
                    await category.set_permissions(target, overwrite=None)
            except discord.DiscordException:
                logging.warning("Impossible de nettoyer les permissions du ticket.")

        del state["tickets"]["channels"][str(interaction.channel_id)]
        save_state()

        await interaction.response.send_message("Le ticket va etre supprime.")
        await asyncio.sleep(1.5)
        await interaction.channel.delete(reason="Ticket ferme")


async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    category = await resolve_channel(guild, TICKETS_CATEGORY_ID)

    if not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message(
            "La categorie de tickets est introuvable.",
            ephemeral=True,
        )
        return

    state["tickets"]["counter"] += 1
    ticket_number = str(state["tickets"]["counter"]).zfill(4)
    username = re.sub(r"[^a-z0-9_-]", "", interaction.user.name.lower())[:20] or "membre"
    channel_name = f"{username}-{ticket_number}"

    await category.set_permissions(
        interaction.user,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
    )

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        reason=f"Creation ticket {ticket_type}",
    )

    await channel.set_permissions(
        interaction.user,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
    )

    state["tickets"]["channels"][str(channel.id)] = {
        "owner_id": interaction.user.id,
        "claimed_by": None,
        "type": ticket_type,
    }
    save_state()

    await channel.send(
        content=interaction.user.mention,
        embed=build_ticket_embed(ticket_type),
        view=TicketActionsView(),
    )

    await interaction.response.edit_message(
        content=f"Ton ticket a ete cree : {channel.mention}",
        embed=None,
        view=None,
    )


async def fetch_main_guild() -> discord.Guild:
    if not GUILD_ID:
        raise RuntimeError("La variable GUILD_ID est obligatoire.")

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise RuntimeError("Le bot ne voit pas le serveur configure.")
    return guild


async def send_persistent_panels(guild: discord.Guild):
    regulation_channel = await resolve_channel(guild, CHANNEL_IDS["regulation"])
    anti_scam_channel = await resolve_channel(guild, CHANNEL_IDS["anti_scam"])
    tickets_channel = await resolve_channel(guild, CHANNEL_IDS["tickets_panel"])

    if not state["sent_panels"]["regulation"] and isinstance(regulation_channel, discord.TextChannel):
        await regulation_channel.send(embed=build_regulation_embed())
        state["sent_panels"]["regulation"] = True
        logging.info("Reglement envoye dans le salon %s", regulation_channel.id)

    if not state["sent_panels"]["anti_scam"] and isinstance(anti_scam_channel, discord.TextChannel):
        await anti_scam_channel.send(embed=build_anti_scam_embed())
        state["sent_panels"]["anti_scam"] = True
        logging.info("Embed anti-arnaque envoye dans le salon %s", anti_scam_channel.id)

    if not state["sent_panels"]["tickets"] and isinstance(tickets_channel, discord.TextChannel):
        await tickets_channel.send(embed=build_ticket_panel_embed(), view=TicketPanelView())
        state["sent_panels"]["tickets"] = True
        logging.info("Panel tickets envoye dans le salon %s", tickets_channel.id)

    save_state()


async def update_voice_member_count(guild: discord.Guild):
    voice_channel = await resolve_channel(guild, VOICE_CHANNEL_ID)
    if not isinstance(voice_channel, discord.VoiceChannel):
        logging.warning("Salon vocal introuvable ou mauvais type: %s", VOICE_CHANNEL_ID)
        return

    member_count = guild.member_count or sum(1 for member in guild.members if not member.bot)
    new_name = f"Membres : {member_count}"

    if voice_channel.name != new_name:
        await voice_channel.edit(
            name=new_name,
            reason="Mise a jour automatique du nombre de membres",
        )


async def remove_member_messages(guild: discord.Guild, user_id: int):
    for channel in guild.text_channels:
        try:
            async for message in channel.history(limit=None):
                if message.author.id == user_id:
                    try:
                        await message.delete()
                    except discord.DiscordException:
                        pass
        except discord.DiscordException:
            logging.warning("Suppression impossible dans #%s", channel.name)


@tasks.loop(minutes=1)
async def cleanup_expired_bans():
    now = int(time.time())
    guild = await fetch_main_guild()
    active_bans = []

    for temp_ban in state["temp_bans"]:
        if temp_ban["expires_at"] > now:
            active_bans.append(temp_ban)
            continue

        try:
            await guild.unban(
                discord.Object(id=temp_ban["user_id"]),
                reason="Fin du bannissement temporaire automatique",
            )
        except discord.DiscordException:
            logging.warning("Deban impossible pour %s", temp_ban["user_id"])

    if len(active_bans) != len(state["temp_bans"]):
        state["temp_bans"] = active_bans
        save_state()


@bot.event
async def on_ready():
    logging.info("%s est connecte en tant que Copperia Bot.", bot.user)
    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionsView())

    try:
        guild = await fetch_main_guild()
        await send_persistent_panels(guild)
        await update_voice_member_count(guild)
        logging.info("Initialisation terminee pour le serveur %s", guild.id)
    except Exception:
        logging.exception("Echec pendant l'initialisation du bot")

    if not cleanup_expired_bans.is_running():
        cleanup_expired_bans.start()


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    welcome_channel = member.guild.get_channel(CHANNEL_IDS["welcome"])
    if isinstance(welcome_channel, discord.TextChannel):
        await welcome_channel.send(embed=build_welcome_embed(member))

    await update_voice_member_count(member.guild)


@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    await update_voice_member_count(member.guild)


@bot.event
async def on_message(message: discord.Message):
    if not message.guild or message.author.bot or message.guild.id != GUILD_ID:
        return

    if message.channel.id == CHANNEL_IDS["anti_scam"]:
        try:
            await message.delete()
        except discord.DiscordException:
            pass

        await remove_member_messages(message.guild, message.author.id)

        expires_at = int(time.time()) + TEMP_BAN_DURATION_SECONDS
        state["temp_bans"] = [
            entry for entry in state["temp_bans"] if entry["user_id"] != message.author.id
        ]
        state["temp_bans"].append(
            {"user_id": message.author.id, "expires_at": expires_at}
        )
        save_state()

        try:
            await message.guild.ban(
                message.author,
                reason="Message dans le salon anti-arnaque",
            )
        except discord.DiscordException:
            logging.warning("Ban impossible pour %s", message.author.id)

    await bot.process_commands(message)


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("La variable DISCORD_TOKEN est obligatoire.")

    bot.run(token)
