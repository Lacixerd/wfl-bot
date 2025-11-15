import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import io
import re
import json
import os
# import pytz # PYTZ KALDIRILDI
from timezone import gmtBasedTimezones # timezone.py'dan import eklendi
from discord.ui import View, Button, Modal, TextInput
import asyncio

# configs.json yükleme ve kaydetme yardımcı fonksiyonları
CONFIG_FILE = 'configs.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Zaman dilimi ayrıştırma yardımcısı
def parse_custom_timezone_to_object(tz_input_str: str):
    # 1. Doğrudan `gmtBasedTimezones` sözlüğünde ara (kullanıcının girdiği orijinal haliyle)
    offset_hours = gmtBasedTimezones.get(tz_input_str)
    if offset_hours is not None:
        try:
            return datetime.timezone(datetime.timedelta(hours=offset_hours))
        except ValueError: # Geçersiz saat ofseti (çok büyük/küçük)
            print(f"Invalid offset hours from dictionary for {tz_input_str}: {offset_hours}")
            return None # Hatalı yapılandırma durumunda None döndür

    # 2. `gmtBasedTimezones` sözlüğünde büyük harfli versiyonunu ara
    # (Sözlükteki anahtarlar genellikle büyük harf olduğu için)
    offset_hours_upper = gmtBasedTimezones.get(tz_input_str.upper())
    if offset_hours_upper is not None:
        try:
            return datetime.timezone(datetime.timedelta(hours=offset_hours_upper))
        except ValueError:
            print(f"Invalid offset hours from dictionary (uppercase) for {tz_input_str.upper()}: {offset_hours_upper}")
            return None

    # 3. Sözlükte bulunamazsa, GMT/UTC/+/-/ H:M formatları için regex ile dene
    # Regex için normalleştirilmiş string (büyük harf, boşluksuz)
    tz_str_for_regex = tz_input_str.upper().replace(" ", "")

    # Format: GMT+H, GMT+H:M, UTC+H, UTC+H:M, +H, +H:M veya bunların - versiyonları
    match = re.fullmatch(r"(?:GMT|UTC)?([+-])(\d{1,2})(?:[:\.](\d{1,2}))?", tz_str_for_regex)
    
    if match:
        sign_char = match.group(1)
        hours_str = match.group(2)
        minutes_str = match.group(3)
        
        try:
            hours = int(hours_str)
            minutes = int(minutes_str) if minutes_str else 0
        except ValueError: # Sayıya dönüşüm hatası
            print(f"Invalid number format in regex for {tz_input_str}")
            return None

        if not (0 <= hours <= 14 and 0 <= minutes <= 59): # Geniş bir ofset aralığı
            print(f"Invalid offset hours/minutes from regex for {tz_input_str}")
            return None

        offset_seconds = (hours * 3600 + minutes * 60)
        if sign_char == '-':
            offset_seconds *= -1
        
        try:
            return datetime.timezone(datetime.timedelta(seconds=offset_seconds))
        except ValueError: # Örneğin timedelta için çok büyük/küçük değerler
            print(f"Invalid offset seconds from regex for {tz_input_str}")
            return None
    
    print(f"Could not parse timezone string: {tz_input_str}")
    return None # Tanınmayan format

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.launch_time = datetime.datetime.utcnow()  # Bot'un başlangıç zamanını ekle
        self.active_duty_timers = {} # Aktif görevlerin zamanlayıcılarını tutmak için
    
    async def update_duty_embed(self, guild_id: str, user_id: str, duty_id: str):
        """Periodically updates the elapsed time on an active duty embed."""
        config = load_config()
        try:
            guild_settings = config["duty_settings"][guild_id]
            active_duty = guild_settings.get("active_duties", {}).get(user_id)

            if not active_duty or active_duty["id"] != duty_id or not active_duty.get("status_message_id"):
                # Görev artık aktif değil veya bulunamadı, zamanlayıcıyı durdur
                timer_key = (guild_id, user_id, duty_id)
                if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
                    self.active_duty_timers[timer_key].cancel()
                    del self.active_duty_timers[timer_key]
                return

            channel_id = active_duty.get("original_channel_id")
            message_id = active_duty.get("status_message_id")
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return # Kanal bulunamadı
            
            message = await channel.fetch_message(message_id)
            if not message or not message.embeds:
                return # Mesaj veya embed bulunamadı

            original_embed = message.embeds[0]
            
            time_started_dt = datetime.datetime.fromtimestamp(active_duty["time_started_timestamp"], tz=datetime.timezone.utc)
            current_time_utc = datetime.datetime.now(datetime.timezone.utc)
            elapsed_seconds = (current_time_utc - time_started_dt).total_seconds()

            days, remainder = divmod(elapsed_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            elapsed_str = f"{int(hours):02d}h {int(minutes):02d}m {int(seconds):02d}s"
            if days > 0:
                elapsed_str = f"{int(days)}d " + elapsed_str
            
            new_description = f"Started at: {active_duty['time_started']}\nElapsed Time: {elapsed_str}"
            
            # Sadece açıklama değiştiyse yeni embed oluşturmaya gerek yok, var olanı kullan
            updated_embed = original_embed.copy()
            updated_embed.description = new_description
            
            await message.edit(embed=updated_embed)

        except discord.NotFound:
            # Mesaj bulunamadı, muhtemelen silindi. Zamanlayıcıyı durdur.
            timer_key = (guild_id, user_id, duty_id)
            if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
                self.active_duty_timers[timer_key].cancel()
                del self.active_duty_timers[timer_key]
            # Belki config'den de görevi temizlemek gerekebilir, kullanıcı manuel sildiyse.
        except Exception as e:
            print(f"Error updating duty embed for {user_id} in {guild_id}: {e}")

    def start_duty_timer(self, interaction_or_message, duty_data: dict):
        guild_id = str(interaction_or_message.guild.id)
        user_id = str(duty_data["user_id"])
        duty_id = duty_data["id"]
        timer_key = (guild_id, user_id, duty_id)

        async def timer_task():
            while True:
                await self.update_duty_embed(guild_id, user_id, duty_id)
                await asyncio.sleep(30) # Her 30 saniyede bir güncelle
        
        # Eğer zaten bu görev için bir zamanlayıcı varsa, önce onu iptal et
        if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
            self.active_duty_timers[timer_key].cancel()
        
        task = self.bot.loop.create_task(timer_task())
        self.active_duty_timers[timer_key] = task

    async def on_interaction_general(self, interaction: discord.Interaction):
        if not interaction.data or "custom_id" not in interaction.data:
            return

        custom_id = interaction.data["custom_id"]
        config = load_config()

        if custom_id.startswith("duty_setup_"):
            await interaction.response.send_modal(DutySetupModal())
        
        elif custom_id.startswith("supported_timezones_"):
            await interaction.response.defer(ephemeral=True)
            # timezone.py'dan gmtBasedTimezones zaten dosyanın başında import edilmiş olmalı.
            
            if not gmtBasedTimezones:
                await interaction.followup.send("Currently, no timezones are listed in the configuration.", ephemeral=True)
                return

            # Sözlükteki anahtarları al ve sırala (isteğe bağlı, daha iyi görünüm için)
            sorted_timezones = sorted(gmtBasedTimezones.keys())
            
            # Mesajı oluştur
            # Discord mesaj karakter limiti (2000) ve embed açıklama limiti (4096) göz önünde bulundurulmalı.
            # Basit bir liste için doğrudan string birleştirme yeterli olacaktır.
            message_content = "**Supported Timezones:**\n"
            message_content += "\n".join([f"- `{tz}`" for tz in sorted_timezones])

            # Eğer mesaj çok uzunsa, parçalara ayırmak veya daha kısa bir özet göstermek gerekebilir.
            # Şimdilik tamamını göndermeyi deneyeceğiz.
            if len(message_content) > 1900: # Biraz pay bırakalım
                # Çok uzunsa, bir kısmını veya farklı bir mesaj gönder.
                # Bu örnekte ilk N tanesini alıp uyarı ekleyebiliriz veya sayfalandırma yapılabilir.
                # Şimdilik basit tutalım:
                partial_list = "\n".join([f"- `{tz}`" for tz in sorted_timezones[:50]]) # İlk 50 tanesi
                message_content = "**Supported Timezones (showing first 50 due to length):**\n" + partial_list + "\n...and more."
            
            await interaction.followup.send(message_content, ephemeral=True)

        elif custom_id.startswith("cancel_duty_"): # YENİ: Aktif görevi iptal etme/temizleme
            await interaction.response.defer(ephemeral=True)
            parts = custom_id.split("_") # cancel, duty, guildid, userid
            
            if len(parts) == 4:
                guild_id_str = parts[2]
                user_id_str = parts[3]

                if str(interaction.user.id) != user_id_str and not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("You can only cancel your own duties, or you need administrator permissions.", ephemeral=True)
                    return
                
                try:
                    guild_settings = config.get("duty_settings", {}).get(guild_id_str, {})
                    active_duty = guild_settings.get("active_duties", {}).get(user_id_str)

                    if active_duty: # Sadece aktif bir görev varsa işlem yap
                        # Zamanlayıcıyı durdur (duty_id artık custom_id'de yok, active_duty içinden al)
                        duty_id_for_timer = active_duty.get("id")
                        if duty_id_for_timer:
                            timer_key = (guild_id_str, user_id_str, duty_id_for_timer)
                            if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
                                self.active_duty_timers[timer_key].cancel()
                                del self.active_duty_timers[timer_key]
                        
                        # Aktif görev embed mesajını sil
                        if active_duty.get("status_message_id") and active_duty.get("original_channel_id"):
                            try:
                                channel = self.bot.get_channel(active_duty["original_channel_id"])
                                if channel:
                                    status_message = await channel.fetch_message(active_duty["status_message_id"])
                                    await status_message.delete()
                            except discord.NotFound:
                                pass 
                            except discord.Forbidden:
                                print(f"Warning: Could not delete status message for user {user_id_str} in guild {guild_id_str} due to permissions.")
                            except Exception as e:
                                print(f"Error deleting status message for user {user_id_str} in guild {guild_id_str}: {e}")                            

                        # Aktif görevi config dosyasından sil
                        if user_id_str in config.get("duty_settings", {}).get(guild_id_str, {}).get("active_duties", {}):
                            del config["duty_settings"][guild_id_str]["active_duties"][user_id_str]
                            save_config(config)
                            await interaction.followup.send("Duty has been cleared. You can now start a new one by sending the first photo.", ephemeral=True)
                        else:
                            await interaction.followup.send("Duty already cleared from config. Ready for a new duty.", ephemeral=True)
                    else:
                        await interaction.followup.send("No active duty found to clear.", ephemeral=True)
                except Exception as e:
                    print(f"Error during active duty cancellation (custom_id: {custom_id}): {e}")
                    await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)
            else:
                await interaction.followup.send("Invalid cancel_duty command format.", ephemeral=True)

        elif custom_id.startswith("duty_delete_dm_"): # ESKİ DM SİLME (ayrı tutuluyor)
            await interaction.response.defer(ephemeral=True)
            parts = custom_id.split("_")
            # Format: duty_delete_dm_authorid_dmmessageid (5 bölüm)
            if len(parts) == 5 and parts[2] == "dm":
                dm_author_id_str = parts[3]
                dm_message_id_str = parts[4]

                if str(interaction.user.id) != dm_author_id_str:
                    await interaction.followup.send("This isn't for you!", ephemeral=True)
                    return
                try:
                    if interaction.message and str(interaction.message.id) == dm_message_id_str:
                        await interaction.message.delete()
                        await interaction.followup.send("Summary deleted.", ephemeral=True, delete_after=5)
                    else:
                        await interaction.followup.send("Could not delete the summary.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send("I couldn't delete the summary message in DM.", ephemeral=True)
                except Exception as e:
                    print(f"Error deleting DM summary (custom_id: {custom_id}): {e}")
                    await interaction.followup.send("An error occurred while deleting the summary.", ephemeral=True)
            else:
                await interaction.followup.send("Invalid DM delete command format.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = load_config()
        if "duty_settings" not in config or str(message.guild.id) not in config["duty_settings"]:
            return

        guild_settings = config["duty_settings"][str(message.guild.id)]
        if "duty_channel_id" not in guild_settings or message.channel.id != guild_settings["duty_channel_id"]:
            return

        # Arşiv kanalı ayarlanmış mı kontrol et
        archive_channel_id = guild_settings.get("duty_archive_channel_id")
        archive_channel = None
        if archive_channel_id:
            archive_channel = self.bot.get_channel(archive_channel_id)
            if not archive_channel:
                pass 

        # Kullanıcı bilgilerini al
        user_info = guild_settings.get("user_info", {}).get(str(message.author.id))
        if not user_info:
            try:
                await message.author.send(
                    f"Please set up your duty information first using the \"Setup & Edit Info\" button in the #{message.channel.name} channel on the {message.guild.name} server."
                )
            except discord.Forbidden:
                # DM gönderilemiyorsa, kanala geçici bir mesaj gönderilebilir
                await message.channel.send(f"{message.author.mention}, please set up your duty information first using the \"Setup & Edit Info\" button!", delete_after=20)
            return

        # Sadece fotoğraf eklentisi olan mesajları işle
        if not message.attachments or not any(att.content_type.startswith('image/') for att in message.attachments):
            return
        
        attachment = message.attachments[0]
        original_image_url = attachment.url # Orijinal URL her zaman elimizde olsun
        
        archived_image_url = original_image_url # Varsayılan olarak orijinal URL

        if archive_channel and message.attachments:
            try:
                file_to_archive = await attachment.to_file()
                archived_message = await archive_channel.send(file=file_to_archive)
                if archived_message.attachments:
                    archived_image_url = archived_message.attachments[0].url
                else:
                    pass # Hata durumunda orijinal URL kullanılır
            except discord.Forbidden:
                pass # Hata durumunda orijinal URL kullanılır
            except Exception as e:
                pass # Hata durumunda orijinal URL kullanılır

        image_url = archived_image_url # Görev takibinde kullanılacak URL
        user_id_str = str(message.author.id)
        guild_id_str = str(message.guild.id)

        # Aktif görevleri yönetmek için guild_settings içinde active_duties alanı oluşturalım
        if "active_duties" not in guild_settings:
            guild_settings["active_duties"] = {}
        
        active_duty = guild_settings["active_duties"].get(user_id_str)

        # Zaman ve timezone işlemleri
        user_timezone_config_str = user_info.get("timezone", "UTC") # Config'den okunan string (örn: "EST", "GMT+3")
        user_tz_object = parse_custom_timezone_to_object(user_timezone_config_str) # datetime.timezone nesnesi veya None döner

        final_display_tz_str = user_timezone_config_str # Başlangıçta kullanıcının girdiği string'i gösterim için kullan

        if user_tz_object is None: # Eğer parse edilemezse
            await message.channel.send(f"{message.author.mention}, your configured timezone '{user_timezone_config_str}' is currently invalid or could not be processed. Please update it via \"Setup & Edit Info\". Using UTC as default for now.", delete_after=20)
            user_tz_object = datetime.timezone.utc # Hesaplamalar için UTC'ye dön
            final_display_tz_str = "UTC" # Gösterim için "UTC" kullan
        
        current_time_utc = datetime.datetime.now(datetime.timezone.utc) # Her zaman UTC tabanlı çalış
        current_time_user_local = current_time_utc.astimezone(user_tz_object) # Kullanıcının zaman dilimine çevir
        
        # Zaman formatında final_display_tz_str kullanılır. Bu ya kullanıcının girdiği string ya da hata durumunda "UTC" olur.
        formatted_time = current_time_user_local.strftime("%H:%M") + f" {final_display_tz_str}"

        if not active_duty: # İlk fotoğraf, yeni görev başlat
            duty_id = f"duty_{message.id}" # Benzersiz bir görev ID'si
            new_duty = {
                "id": duty_id,
                "user_id": user_id_str,
                "user_name": user_info.get("name", message.author.display_name),
                "duty_title": user_info.get("duty_title", "Patrol"),
                "image1_url": image_url,
                "time_started": formatted_time,
                "time_started_timestamp": current_time_utc.timestamp(),
                "image2_url": None,
                "image3_url": None,
                "time_ended": None,
                "status_message_id": None, # Görev durumunu gösteren embed mesajının ID'si
                "archive_message_id": None, # Archive kanalındaki mesajın ID'si
                "original_channel_id": message.channel.id
            }
            guild_settings["active_duties"][user_id_str] = new_duty
            
            # Embed oluştur ve gönder
            embed = discord.Embed(
                title=f"{new_duty['user_name']}'s Active Duty - {new_duty['duty_title']}",
                description=f"Started at: {new_duty['time_started']}\nElapsed Time: Calculating...",
                color=discord.Color.green()
            )
            embed.add_field(name="Tablist Started (1)", value=f"[Link]({new_duty['image1_url']})", inline=False)
            embed.set_footer(text=f"Duty ID: {duty_id}")

            view = discord.ui.View(timeout=None) # Butonlar kalıcı olsun
            cancel_button = discord.ui.Button(label="Cancel & Clear Duty", style=discord.ButtonStyle.danger, custom_id=f"cancel_duty_{guild_id_str}_{user_id_str}")
            view.add_item(cancel_button)

            try:
                status_message = await message.channel.send(embed=embed, view=view)
                new_duty["status_message_id"] = status_message.id
                
                # Archive kanalına da aynı embed'i gönder (buton olmadan)
                if archive_channel:
                    try:
                        archive_embed = discord.Embed(
                            title=embed.title,
                            description=embed.description,
                            color=embed.color
                        )
                        archive_embed.add_field(name="Tablist Started (1)", value=f"[Link]({new_duty['image1_url']})", inline=False)
                        archive_embed.set_footer(text=embed.footer.text)
                        
                        archive_message = await archive_channel.send(embed=archive_embed)
                        new_duty["archive_message_id"] = archive_message.id
                    except Exception as e:
                        print(f"Error sending embed to archive channel: {e}")
                
                save_config(config) # config'i burada kaydet, message ID'leri eklendikten sonra
                # Zamanlayıcıyı başlat
                self.start_duty_timer(interaction_or_message=message, duty_data=new_duty)
            except Exception as e:
                print(f"Error sending duty status message: {e}")
                # Hata durumunda aktif görevi temizle veya logla
                if user_id_str in guild_settings["active_duties"]:
                    del guild_settings["active_duties"][user_id_str]
                    save_config(config)
            
            try: # Orijinal mesajı silmeyi dene
                await message.delete()
            except discord.Forbidden:
                pass
            except discord.NotFound:
                pass

        elif not active_duty["image2_url"]: # İkinci fotoğraf
            active_duty["image2_url"] = image_url
            # Embed mesajını güncelle
            try:
                status_message = await message.channel.fetch_message(active_duty["status_message_id"])
                original_embed = status_message.embeds[0]
                
                new_embed = discord.Embed(
                    title=original_embed.title,
                    description=original_embed.description, # Zamanlayıcı bunu güncelleyecek
                    color=original_embed.color
                )
                new_embed.add_field(name="Tablist Started (1)", value=f"[Link]({active_duty['image1_url']})", inline=False)
                new_embed.add_field(name="Duty Image (2)", value=f"[Link]({active_duty['image2_url']})", inline=False)
                if original_embed.footer:
                    new_embed.set_footer(text=original_embed.footer.text)
                
                await status_message.edit(embed=new_embed)
                
                # Archive kanalındaki mesajı da güncelle
                if archive_channel and active_duty.get("archive_message_id"):
                    try:
                        archive_message = await archive_channel.fetch_message(active_duty["archive_message_id"])
                        archive_embed = discord.Embed(
                            title=new_embed.title,
                            description=new_embed.description,
                            color=new_embed.color
                        )
                        archive_embed.add_field(name="Tablist Started (1)", value=f"[Link]({active_duty['image1_url']})", inline=False)
                        archive_embed.add_field(name="Duty Image (2)", value=f"[Link]({active_duty['image2_url']})", inline=False)
                        if new_embed.footer:
                            archive_embed.set_footer(text=new_embed.footer.text)
                        
                        await archive_message.edit(embed=archive_embed)
                    except discord.NotFound:
                        print(f"Archive message not found for duty {active_duty['id']}")
                    except Exception as e:
                        print(f"Error updating archive embed: {e}")
                
                save_config(config)
            except discord.NotFound:
                await message.channel.send(f"{message.author.mention}, could not find the original duty status message. Please start a new duty if needed.", delete_after=20)
                del guild_settings["active_duties"][user_id_str]
                save_config(config)
            except Exception as e:
                print(f"Error updating duty status message for 2nd image: {e}")
            
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            except discord.NotFound:
                pass

        elif not active_duty["image3_url"]: # Üçüncü fotoğraf, görevi bitir
            active_duty["image3_url"] = image_url
            active_duty["time_ended"] = formatted_time
            
            # Zamanlayıcıyı durdur (eğer çalışıyorsa)
            timer_key = (guild_id_str, user_id_str, active_duty["id"])
            if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
                self.active_duty_timers[timer_key].cancel()
                del self.active_duty_timers[timer_key]

            # Embed mesajını son kez güncelle ve butonları değiştir
            try:
                status_message = await message.channel.fetch_message(active_duty["status_message_id"])
                original_embed = status_message.embeds[0]
                
                # Geçen süreyi son kez hesapla
                time_started_dt = datetime.datetime.fromtimestamp(active_duty["time_started_timestamp"], tz=datetime.timezone.utc)
                elapsed_seconds = (current_time_utc - time_started_dt).total_seconds()
                days, remainder = divmod(elapsed_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                elapsed_str = f"{int(hours):02d}h {int(minutes):02d}m {int(seconds):02d}s"
                if days > 0:
                    elapsed_str = f"{int(days)}d " + elapsed_str

                final_description = f"Started: {active_duty['time_started']}\nEnded: {active_duty['time_ended']}\nTotal Duration: {elapsed_str}"

                final_embed = discord.Embed(
                    title=original_embed.title.replace("Active", "Completed"),
                    description=final_description,
                    color=discord.Color.gold()
                )
                final_embed.add_field(name="Tablist Started (1)", value=f"[Link]({active_duty['image1_url']})", inline=False)
                final_embed.add_field(name="Duty Image (2)", value=f"[Link]({active_duty['image2_url']})", inline=False)
                final_embed.add_field(name="Tablist Ended (3)", value=f"[Link]({active_duty['image3_url']})", inline=False)
                if original_embed.footer:
                    final_embed.set_footer(text=original_embed.footer.text + " - Completed")

                # Butonları kaldır
                await status_message.edit(embed=final_embed, view=None)
                
                # Archive kanalındaki mesajı da son kez güncelle
                if archive_channel and active_duty.get("archive_message_id"):
                    try:
                        archive_message = await archive_channel.fetch_message(active_duty["archive_message_id"])
                        archive_final_embed = discord.Embed(
                            title=final_embed.title,
                            description=final_description,
                            color=discord.Color.gold()
                        )
                        archive_final_embed.add_field(name="Tablist Started (1)", value=f"[Link]({active_duty['image1_url']})", inline=False)
                        archive_final_embed.add_field(name="Duty Image (2)", value=f"[Link]({active_duty['image2_url']})", inline=False)
                        archive_final_embed.add_field(name="Tablist Ended (3)", value=f"[Link]({active_duty['image3_url']})", inline=False)
                        if final_embed.footer:
                            archive_final_embed.set_footer(text=final_embed.footer.text)
                        
                        await archive_message.edit(embed=archive_final_embed)
                    except discord.NotFound:
                        print(f"Archive message not found for completed duty {active_duty['id']}")
                    except Exception as e:
                        print(f"Error updating final archive embed: {e}")

                # Kanal mesajını silmeden önce ID'sini alalım
                status_message_to_delete_id = active_duty.get("status_message_id")
                original_channel_id = active_duty.get("original_channel_id")

                # Kullanıcıya DM ile formatı gönder (Kanal mesajını silmeden ÖNCE)
                duty_format = f"""
Username: {active_duty['user_name']}
Duty: {active_duty['duty_title']}
{active_duty['image2_url']}

Time Started: {active_duty['time_started']}
Tablist Started: {active_duty['image1_url']}

Time Ended: {active_duty['time_ended']}
Tablist Ended: {active_duty['image3_url']}
"""
                dm_view = discord.ui.View(timeout=None)
                sent_dm_message = None
                try:
                    dm_message_content = f"Your duty submission:\n```{duty_format}```"
                    sent_dm_message = await message.author.send(content=dm_message_content)
                    await sent_dm_message.edit(view=dm_view)
                except discord.Forbidden:
                    await message.channel.send(f"{message.author.mention}, I couldn't DM you the duty summary. Please check your DMs.", delete_after=30)
                except Exception as e:
                    print(f"Error sending DM for duty completion: {e}")
                
                # Şimdi kanal mesajını sil
                if status_message_to_delete_id and original_channel_id:
                    try:
                        channel = self.bot.get_channel(original_channel_id)
                        if channel:
                            status_message_obj = await channel.fetch_message(status_message_to_delete_id)
                            await status_message_obj.delete()
                            print(f"Successfully deleted status message {status_message_to_delete_id} for completed duty.")
                    except discord.NotFound:
                        print(f"Status message {status_message_to_delete_id} not found for deletion (completed duty).")
                    except discord.Forbidden:
                        print(f"Could not delete status message {status_message_to_delete_id} due to permissions (completed duty).")
                    except Exception as e:
                        print(f"Error deleting status message {status_message_to_delete_id} (completed duty): {e}")
                
                # Aktif görevi temizle (config'den)
                if user_id_str in guild_settings.get("active_duties", {}):
                    del guild_settings["active_duties"][user_id_str]
                save_config(config)

            except discord.NotFound:
                await message.channel.send(f"{message.author.mention}, could not find the original duty status message to finalize. Please start a new duty if needed.", delete_after=20)
                if user_id_str in guild_settings["active_duties"]:
                    del guild_settings["active_duties"][user_id_str]
                    save_config(config)
            except Exception as e:
                print(f"Error finalizing duty status message for 3rd image: {e}")
            
            try:
                await message.delete() # Tekrar aktif hale getirildi
            except discord.Forbidden:
                pass
            except discord.NotFound:
                pass
        else:
            # Kullanıcının zaten 3 fotoğrafı da tamamlanmış bir görevi var ama yeni fotoğraf gönderiyor
            # Veya beklenmedik bir durum.
            await message.channel.send(f"{message.author.mention}, you already have a completed duty or an unexpected error occurred. Please start a new duty if you wish.", delete_after=30)
            try:
                await message.delete() # Tekrar aktif hale getirildi
            except: pass

    @app_commands.command(name="ping", description="Shows the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Latency: {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="avatar", description="Shows a user's avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows a user's avatar"""
        user = user or interaction.user
        
        embed = discord.Embed(
            title=f"{user.name}'s Avatar",
            color=discord.Color.blue()
        )
        
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        embed.set_image(url=avatar_url)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Shows information about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        """Shows information about the bot"""
        bot_user = self.bot.user
        
        # Calculate uptime
        current_time = datetime.datetime.utcnow()
        uptime = current_time - self.bot.launch_time
        days, remainder = divmod(int(uptime.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Get guild count and member count
        guild_count = len(self.bot.guilds)
        member_count = sum(g.member_count for g in self.bot.guilds)
        
        embed = discord.Embed(
            title=f"{bot_user.name} Information",
            description="A multipurpose Discord bot",
            color=discord.Color.blue()
        )
        
        if bot_user.avatar:
            embed.set_thumbnail(url=bot_user.avatar.url)
            
        embed.add_field(name="Bot ID", value=bot_user.id, inline=True)
        embed.add_field(name="Created On", value=f"<t:{int(bot_user.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Servers", value=guild_count, inline=True)
        embed.add_field(name="Users", value=member_count, inline=True)
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channelinfo", description="Shows information about a channel")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Shows information about a channel"""
        channel = channel or interaction.channel
        
        # Get channel type
        channel_type = str(channel.type).replace("_", " ").title()
        
        # Get channel creation time
        created_at = int(channel.created_at.timestamp())
        
        embed = discord.Embed(
            title=f"#{channel.name} Information",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Channel ID", value=channel.id, inline=True)
        embed.add_field(name="Type", value=channel_type, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="Position", value=channel.position, inline=True)
        embed.add_field(name="NSFW", value="Yes" if channel.is_nsfw() else "No", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="Topic", value=channel.topic or "No topic set", inline=False)
            embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay} seconds" if channel.slowmode_delay else "Disabled", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="djsdocs", description="Search the discord.js documentation")
    async def djsdocs(self, interaction: discord.Interaction, query: str):
        """Search the discord.js documentation"""
        await interaction.response.defer()
        
        base_url = "https://djsdocs.sorta.moe/v2/embed"
        
        # Create search query
        params = {
            "src": "stable",
            "q": query
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("Failed to search the documentation.")
                
                data = await resp.json()
                
                if not data:
                    return await interaction.followup.send(f"No results found for `{query}`.")
                
                # Convert to Discord embed
                embed = discord.Embed.from_dict(data)
                embed.set_footer(text=f"Requested by {interaction.user.name}")
                
                await interaction.followup.send(embed=embed)

    @app_commands.command(name="roleinfo", description="Shows information about a role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Shows information about a role"""
        # Get role creation time
        created_at = int(role.created_at.timestamp())
        
        # Format permissions
        permissions = []
        for perm, value in role.permissions:
            if value:
                permissions.append(perm.replace("_", " ").title())
        
        # Get members with this role
        member_count = len(role.members)
        
        embed = discord.Embed(
            title=f"{role.name} Information",
            color=role.color
        )
        
        embed.add_field(name="Role ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=f"#{role.color.value:06x}".upper(), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Members", value=member_count, inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        if permissions:
            # Format permissions nicely
            perm_text = ", ".join(permissions)
            if len(perm_text) > 1024:
                perm_text = perm_text[:1021] + "..."
            embed.add_field(name="Key Permissions", value=perm_text, inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rolememberinfo", description="Lists members with a specific role")
    async def rolememberinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Lists members with a specific role"""
        members = role.members
        
        if not members:
            return await interaction.response.send_message(f"No members have the role {role.mention}.")
        
        # Sort members by name
        members.sort(key=lambda m: m.name.lower())
        
        embed = discord.Embed(
            title=f"Members with {role.name} Role",
            description=f"Total members: {len(members)}",
            color=role.color
        )
        
        # Create a list of member names
        member_names = [f"{m.name}" for m in members]
        
        # Split into chunks if too many members
        chunks = [member_names[i:i + 20] for i in range(0, len(member_names), 20)]
        
        for i, chunk in enumerate(chunks):
            if i < 5:  # Limit to 5 fields (100 members)
                embed.add_field(name=f"Members {i*20+1}-{i*20+len(chunk)}", value="\n".join(chunk), inline=True)
        
        if len(chunks) > 5:
            embed.add_field(name="Note", value=f"Showing 100/{len(members)} members", inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverav", description="Shows the server's icon")
    async def serverav(self, interaction: discord.Interaction):
        """Shows the server's icon"""
        guild = interaction.guild
        
        if not guild.icon:
            return await interaction.response.send_message("This server doesn't have an icon.")
        
        embed = discord.Embed(
            title=f"{guild.name} Server Icon",
            color=discord.Color.blue()
        )
        
        embed.set_image(url=guild.icon.url)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Shows information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Shows information about the server"""
        guild = interaction.guild
        
        # Get creation time
        created_at = int(guild.created_at.timestamp())
        
        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Get member counts
        total_members = guild.member_count
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.chunked else "Unknown"
        
        # Get role count
        roles = len(guild.roles) - 1  # Subtract @everyone
        
        # Get boost info
        boost_level = guild.premium_tier
        boosts = guild.premium_subscription_count
        
        embed = discord.Embed(
            title=f"{guild.name} Server Information",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        embed.add_field(name="Members", value=total_members, inline=True)
        embed.add_field(name="Channels", value=f"📝 {text_channels} | 🔊 {voice_channels} | 📁 {categories}", inline=True)
        embed.add_field(name="Roles", value=roles, inline=True)
        
        embed.add_field(name="Boost Level", value=f"Level {boost_level} ({boosts} boosts)", inline=True)
        
        if guild.features:
            features = ", ".join(f.replace("_", " ").title() for f in guild.features)
            embed.add_field(name="Features", value=features, inline=False)
            
        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)
            
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ss", description="Takes a screenshot of a website")
    async def ss(self, interaction: discord.Interaction, url: str):
        """Takes a screenshot of a website"""
        await interaction.response.defer()
        
        # Add https:// if not present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Use a screenshot API
        screenshot_url = f"https://image.thum.io/get/width/1200/crop/800/fullpage/{url}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(screenshot_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("Failed to take a screenshot of the website.")
                    
                    image_data = await resp.read()
                    
                    # Create file
                    file = discord.File(io.BytesIO(image_data), filename="screenshot.png")
                    
                    embed = discord.Embed(
                        title="Website Screenshot",
                        description=url,
                        color=discord.Color.blue()
                    )
                    
                    embed.set_image(url="attachment://screenshot.png")
                    embed.set_footer(text=f"Requested by {interaction.user.name}")
                    
                    await interaction.followup.send(embed=embed, file=file)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command(name="twitter", description="Get information about a Twitter/X user")
    async def twitter(self, interaction: discord.Interaction, username: str):
        """Get information about a Twitter/X user"""
        await interaction.response.defer()
        
        # Clean the username
        username = username.replace("@", "").strip()
        
        # Use Twitter API services
        twitter_url = f"https://api.twitter.com/2/users/by/username/{username}"
        
        # For demonstration purposes, we'll just show a formatted result
        # In practice, you'd need a Twitter API key
        embed = discord.Embed(
            title=f"@{username}",
            description="This command requires Twitter API credentials which are not available.",
            color=discord.Color.blue(),
            url=f"https://twitter.com/{username}"
        )
        
        embed.add_field(name="Note", value="Due to Twitter API changes, this command would require a paid API key.", inline=False)
        embed.add_field(name="Profile Link", value=f"[Click to view profile](https://twitter.com/{username})", inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="whois", description="Shows detailed information about a user")
    async def whois(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows detailed information about a user"""
        user = user or interaction.user
        
        # Get join position
        join_position = sorted(interaction.guild.members, key=lambda m: m.joined_at or datetime.datetime.now()).index(user) + 1
        
        # Get dates
        created_at = int(user.created_at.timestamp())
        joined_at = int(user.joined_at.timestamp()) if user.joined_at else None
        
        # Get status and activity
        status = str(user.status).title() if hasattr(user, "status") else "Unknown"
        activity = user.activity.name if user.activity else "None"
        
        # Get role list
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        roles.reverse()  # Highest role first
        
        embed = discord.Embed(
            title=f"User Information - {user.name}",
            color=user.color
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="User ID", value=user.id, inline=True)
        embed.add_field(name="Nickname", value=user.nick or "None", inline=True)
        embed.add_field(name="Join Position", value=f"{join_position}{'th' if 4 <= join_position % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(join_position % 10, 'th')}", inline=True)
        
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        if joined_at:
            embed.add_field(name="Joined On", value=f"<t:{joined_at}:F>", inline=True)
        
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Activity", value=activity, inline=True)
        
        if roles:
            embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else ""), inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wikipedia", description="Search Wikipedia for information")
    async def wikipedia(self, interaction: discord.Interaction, query: str):
        """Search Wikipedia for information"""
        await interaction.response.defer()
        
        # Format the query for the API
        search_query = query.replace(" ", "+")
        
        # Wikipedia API endpoint
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_query}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(f"No Wikipedia article found for '{query}'.")
                    
                    data = await resp.json()
                    
                    # Extract information
                    title = data.get("title", "Unknown")
                    extract = data.get("extract", "No information available.")
                    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                    
                    # Limit extract length
                    if len(extract) > 4000:
                        extract = extract[:4000] + "..."
                    
                    # Get thumbnail if available
                    thumbnail = data.get("thumbnail", {}).get("source", None)
                    
                    embed = discord.Embed(
                        title=title,
                        description=extract,
                        color=discord.Color.blue(),
                        url=url
                    )
                    
                    if thumbnail:
                        embed.set_thumbnail(url=thumbnail)
                        
                    embed.set_footer(text=f"From Wikipedia • Requested by {interaction.user.name}")
                    
                    await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command(name="setdutychannel", description="Sets the channel for duty state submissions.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setdutychannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        Sets the channel for duty state submissions.
        Only administrators can use this command.
        Sends an embed message to the specified channel with buttons.
        """
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
            return

        config = load_config()
        if "duty_settings" not in config:
            config["duty_settings"] = {}
        if str(interaction.guild.id) not in config["duty_settings"]:
            config["duty_settings"][str(interaction.guild.id)] = {}

        config["duty_settings"][str(interaction.guild.id)]["duty_channel_id"] = channel.id
        save_config(config)

        embed = discord.Embed(
            title="Waffle Duty State Maker",
            description="Please use the buttons below to setup and edit your duty information. You can not use this feature without setting up your informations. To see the supported timezones, click the \"Supported Timezones\" button. To start a duty, just send your images in the order shown below:\n 1) Tablist Started Image\n 2) Duty Image\n 3) Tablist Ended Image\n\nIf you need more help, please contact the server Bot Manager. Also if you want to report a bug, please contact the server Bot Manager.",
            color=discord.Color.blurple()
        )
        # embed.add_field(name="", value="• Duty Image\n• Tablist Started Image\n• Tablist Ended Image", inline=False)
        embed.set_footer(text="Pro Waffle Bot")
        # embed.set_thumbnail(url="https://i.imgur.com/sFh4hYx.png") # Örnek bir ayar ikonu

        view = discord.ui.View()
        setup_button = discord.ui.Button(label="Setup & Edit Info", style=discord.ButtonStyle.primary, custom_id=f"duty_setup_{interaction.guild.id}")
        supported_tz_button = discord.ui.Button(label="Supported Timezones", style=discord.ButtonStyle.secondary, custom_id=f"supported_timezones_{interaction.guild.id}") # YENİ BUTON

        view.add_item(setup_button)
        view.add_item(supported_tz_button) # YENİ BUTON EKLENDİ

        try:
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"Duty channel set to {channel.mention}. The setup message has been sent.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permissions to send messages in that channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="setdutyarchivechannel", description="Sets the private channel for archiving duty photos.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setdutyarchivechannel(self, interaction: discord.Interaction, archive_channel: discord.TextChannel):
        """
        Sets the private channel where the bot will archive duty photos.
        This channel should ideally be visible only to the bot and administrators.
        """
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
            return

        config = load_config()
        if "duty_settings" not in config:
            config["duty_settings"] = {}
        if str(interaction.guild.id) not in config["duty_settings"]:
            config["duty_settings"][str(interaction.guild.id)] = {}

        config["duty_settings"][str(interaction.guild.id)]["duty_archive_channel_id"] = archive_channel.id
        save_config(config)

        await interaction.response.send_message(f"Duty photo archive channel set to {archive_channel.mention}. Ensure this channel is private and I have send message/attach files permissions there.", ephemeral=True)

    @app_commands.command(name="removedutychannel", description="Resets all duty state settings for this server.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def removedutychannel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        config = load_config()
        guild_id_str = str(interaction.guild.id)

        if "duty_settings" not in config or guild_id_str not in config["duty_settings"]:
            await interaction.followup.send("No duty channel settings found for this server to remove.", ephemeral=True)
            return

        guild_duty_settings = config["duty_settings"].get(guild_id_str, {})

        # 1. Stop active duty timers for this guild
        active_duties_in_guild = guild_duty_settings.get("active_duties", {})
        if active_duties_in_guild:
            # Iterate over a copy of user_ids since we might be modifying the structure indirectly
            for user_id_str, duty_data in list(active_duties_in_guild.items()):
                duty_id = duty_data.get("id")
                if duty_id:
                    timer_key = (guild_id_str, user_id_str, duty_id)
                    if timer_key in self.active_duty_timers and self.active_duty_timers[timer_key]:
                        try:
                            self.active_duty_timers[timer_key].cancel()
                            del self.active_duty_timers[timer_key]
                            print(f"Stopped timer for duty {duty_id} for user {user_id_str} in guild {guild_id_str}")
                        except Exception as e:
                            print(f"Error stopping timer for duty {duty_id} user {user_id_str} guild {guild_id_str}: {e}")
        
        # 2. Attempt to delete the main setup embed message
        duty_channel_id = guild_duty_settings.get("duty_channel_id")
        deleted_setup_message = False
        original_duty_channel_mention = f"channel {duty_channel_id}" # Fallback text
        if duty_channel_id:
            channel = self.bot.get_channel(duty_channel_id)
            if channel:
                original_duty_channel_mention = channel.mention # Use mention if channel is found
                try:
                    async for msg in channel.history(limit=50): # Check last 50 messages
                        if msg.author == self.bot.user and msg.embeds:
                            for embed_in_msg in msg.embeds:
                                if embed_in_msg.title == "Waffle Duty State Maker":
                                    await msg.delete()
                                    deleted_setup_message = True
                                    print(f"Deleted setup message {msg.id} from channel {duty_channel_id}")
                                    break # Found and deleted
                            if deleted_setup_message:
                                break
                except discord.Forbidden:
                    print(f"Could not delete setup message from channel {duty_channel_id} due to permissions.")
                except Exception as e:
                    print(f"Error trying to delete setup message from channel {duty_channel_id}: {e}")
            else:
                print(f"Duty channel {duty_channel_id} not found for deleting setup message.")

        # 3. Remove guild's duty settings from config
        if guild_id_str in config["duty_settings"]:
            del config["duty_settings"][guild_id_str]
        if not config["duty_settings"]: # If "duty_settings" itself becomes empty
            del config["duty_settings"]
        save_config(config)

        feedback_message = f"All duty state settings for this server have been reset."
        if duty_channel_id:
            if deleted_setup_message:
                feedback_message += f" The setup message in the former duty channel {original_duty_channel_mention} has been deleted."
            else:
                feedback_message += f" The setup message in the former duty channel {original_duty_channel_mention} might need to be manually deleted if it still exists (or I couldn't find/delete it)."
        
        await interaction.followup.send(feedback_message, ephemeral=True)

# Setup & Edit Info butonu için Modal
class DutySetupModal(discord.ui.Modal, title='Setup & Edit Duty Info'):
    user_name = discord.ui.TextInput(
        label='Display Name for Duty',
        placeholder='Enter your name or nickname',
        required=True,
        max_length=50
    )
    duty_title = discord.ui.TextInput(
        label='Text for "Duty:" field',
        placeholder='e.g. Guarding the border',
        required=True,
        max_length=100
    )
    timezone_str = discord.ui.TextInput(
        label='Timezone',
        placeholder='Examples: GMT+3, EST, GMT, UTC',
        required=True,
        max_length=50 # Increased for longer TZ names
    )

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(interaction.user.id)

        # Zaman dilimini işle
        raw_tz_str = self.timezone_str.value
        parsed_tz_object = parse_custom_timezone_to_object(raw_tz_str)

        if parsed_tz_object is None:
            await interaction.response.send_message(
                f"The timezone string '{raw_tz_str}' is invalid or not recognized. Please use formats like 'Europe/Istanbul', 'GMT+3', 'UTC-5', or '+3'.", 
                ephemeral=True
            )
            return

        if "duty_settings" not in config:
            config["duty_settings"] = {}
        if guild_id_str not in config["duty_settings"]:
            config["duty_settings"][guild_id_str] = {}
        if "user_info" not in config["duty_settings"][guild_id_str]:
            config["duty_settings"][guild_id_str]["user_info"] = {}

        config["duty_settings"][guild_id_str]["user_info"][user_id_str] = {
            "name": self.user_name.value,
            "duty_title": self.duty_title.value,
            "timezone": raw_tz_str # Kullanıcının girdiği ve geçerli bulunan string'i sakla
        }
        save_config(config)
        await interaction.response.send_message(f"Duty information updated for {interaction.user.mention}! Timezone set to '{raw_tz_str}'.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(f'Oops! Something went wrong: {error}', ephemeral=True)
        # Make sure to log the error further!
        print(error)

async def setup(bot: commands.Bot):
    cog = General(bot)
    bot.add_listener(cog.on_interaction_general, 'on_interaction') # on_interaction_general olarak değiştirelim
    await bot.add_cog(cog) 