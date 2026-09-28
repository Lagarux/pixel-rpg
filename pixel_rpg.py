#!/usr/bin/env python3
"""
KARANLIK TAC'IN LANETI  v5.0  ─  2D Pixel RPG
pip install pygame numpy  |  python pixel_rpg.py

Kontroller:
  WASD / Ok      -> Hareket        F11  -> Tam Ekran
  E              -> Konuş/Etkileşim  ESC -> Çık/Geri
  Space          -> Sınıfa Özel Saldırı
  1 2 3 4        -> Yetenek Kullan
  I              -> Envanter / Ekipman
  Q              -> Görev Günlüğü
  U              -> Nitelik Dağıtımı
  F1             -> Ayarlar
"""
import pygame, sys, math, random, os, json, zlib
from collections import deque
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass

# ─── PyGame mixer başlat (ses için) ─────────────────────────────
try:
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
except Exception:
    pass

SW, SH = 960, 640
TILE    = 32
FPS     = 60
VERSION = "5.0"
TITLE   = "Karanlik Tac'in Laneti"

# ─── Dizinler ────────────────────────────────────────────────────
# Betiğin kendi dizini: SALT-OKUNUR varlıklar (fontlar, ikonlar) için.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PyInstaller onefile: varlıklar geçici _MEIxxxx dizinine açılır.
ASSET_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

def _user_data_dir() -> str:
    """YAZILABİLİR kullanıcı verisi dizini (ayarlar, kayıtlar).

    Oyun Program Files altına kurulduğunda ya da onefile olarak paketlendiğinde
    exe'nin yanına yazmak çalışmaz (izin yok / geçici dizin siliniyor).
    """
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(root, "KaranlikTacinLaneti")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = BASE_DIR  # son çare: eski davranış
    return path

USER_DIR = _user_data_dir()
SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")
SAVE_FILE     = os.path.join(USER_DIR, "save1.json")
SAVE_VERSION  = 1
# v5.0 öncesi ayarlar exe'nin yanındaydı; bir kereliğine oradan da okuyoruz.
LEGACY_SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

def has_save() -> bool:
    return os.path.isfile(SAVE_FILE)

class Settings:
    DEFAULTS = {
        "fullscreen": False, "master_vol": 80, "sfx_vol": 80,
        "music_vol": 60, "language": "TR", "show_fps": False,
    }
    def __init__(self):
        self.data = dict(self.DEFAULTS)
        self.save_failed = False
        self.load()
    def load(self):
        for path in (SETTINGS_FILE, LEGACY_SETTINGS_FILE):
            try:
                with open(path) as f:
                    saved = json.load(f)
                    self.data.update({k:v for k,v in saved.items() if k in self.DEFAULTS})
                return
            except Exception: continue
    def save(self):
        try:
            with open(SETTINGS_FILE,"w") as f: json.dump(self.data,f,indent=2)
            self.save_failed = False
        except Exception:
            self.save_failed = True
    def __getattr__(self,k): return self.data.get(k, self.DEFAULTS.get(k))
    def __setattr__(self,k,v):
        if k in ("data",): super().__setattr__(k,v)
        elif k in self.DEFAULTS: self.data[k]=v
        else: super().__setattr__(k,v)

# Global ayarlar nesnesi
CFG = Settings()

# ─── Yerelleştirme ────────────────────────────────────────────────
# ─── Yerelleştirme ────────────────────────────────────────────────
# Tüm metinler assets/locales/<kod>.json dosyalarında. Eksik anahtar
# Türkçe'ye, o da yoksa anahtarın kendisine düşer — yarım çeviri oyunu
# çökertmez, yalnızca o satır Türkçe kalır.
LOCALE_DIR = os.path.join(ASSET_DIR,"assets","locales")
LANGUAGES = [   # kod, menüde görünen ad, yazı yönü
    ("TR","Türkçe",   "ltr"),
    ("EN","English",  "ltr"),
    ("DE","Deutsch",  "ltr"),
    ("RU","Русский",  "ltr"),
    ("AR","العربية",   "rtl"),
]
LANG_CODES=[c for c,_,_ in LANGUAGES]

try:    # Tam Unicode bidi algoritması varsa onu kullan
    from bidi.algorithm import get_display as _bidi_display
except Exception:
    _bidi_display=None

def _rtl_reorder(text:str)->str:
    """Sağdan sola diller için sözcük sırasını düzeltir.

    SDL_ttf harfleri doğru birleştiriyor (HarfBuzz) ama metni soldan sağa
    diziyor; pygame'in bu sürümünde set_direction yok. Ölçtük: "المستوى 3"
    çizilirken rakam kelimenin SAĞINA ekleniyor, oysa solunda olmalı.
    python-bidi kuruluysa tam algoritma, değilse sözcükleri ters çevirmek
    kısa arayüz metinleri için yeterli bir yaklaşım.
    """
    if _bidi_display is not None:
        try: return _bidi_display(text)
        except Exception: pass
    return " ".join(reversed(text.split(" ")))

class Locale:
    _cache:Dict={}
    FALLBACK="TR"

    @classmethod
    def strings(cls,code)->Dict:
        if code not in cls._cache:
            try:
                with open(os.path.join(LOCALE_DIR,code.lower()+".json"),encoding="utf-8") as f:
                    cls._cache[code]=json.load(f)
            except Exception:
                cls._cache[code]={}
        return cls._cache[code]

    @classmethod
    def current(cls)->str:
        code=CFG.data.get("language","TR")
        return code if code in LANG_CODES else "TR"

    @classmethod
    def direction(cls,code=None)->str:
        code=code or cls.current()
        for c,_,d in LANGUAGES:
            if c==code: return d
        return "ltr"

    @classmethod
    def label(cls,code)->str:
        for c,name,_ in LANGUAGES:
            if c==code: return name
        return code

    @classmethod
    def text(cls,key,*args,default=None)->str:
        code=cls.current()
        s=cls.strings(code).get(key)
        if s is None: s=cls.strings(cls.FALLBACK).get(key)
        if s is None: s=default if default is not None else key
        if args:
            try: s=s%args
            except Exception: pass
        if cls.direction()=="rtl": s=_rtl_reorder(s)
        return s

def T_(key:str,*args,default=None)->str:
    return Locale.text(key,*args,default=default)

# ── Veri tablolarındaki metinler için kısayollar ─────────────────
# Tablolardaki Türkçe metinler kodda yedek olarak duruyor: çeviri dosyası
# bulunamazsa oyun yine okunur kalıyor.
def item_name(k)->str:
    row=ALL_ITEMS.get(k)
    return T_("item.%s.name"%k,default=row[0] if row else k)

def item_desc(k)->str:
    row=ALL_ITEMS.get(k)
    return T_("item.%s.desc"%k,default=row[4] if row and len(row)>4 else "")

def quest_title(n)->str:
    q=QUESTS.get(n)
    return T_("quest.%d.title"%n,default=q[0] if q else "")

def quest_desc(n)->str:
    q=QUESTS.get(n)
    return T_("quest.%d.desc"%n,default=q[1] if q else "")

def class_text(cls_key,field)->str:
    info=CLASS_INFO.get(cls_key,{})
    return T_("class.%s.%s"%(cls_key,field),default=info.get(field,""))

def ability_name(ab)->str:
    return T_("ability.%s"%ab["id"],default=ab["name"])

def stat_name(k)->str:
    return T_("stat.%s"%k,default=dict(STAT_NAMES).get(k,k))

def stat_desc(k)->str:
    return T_("stat.%s.desc"%k,default=STAT_DESCS.get(k,""))

def dlg_line(entry)->str:
    """Diyalog satırı: "anahtar" ya da ("anahtar", arg...) olabilir."""
    if isinstance(entry,(tuple,list)): return T_(entry[0],*entry[1:])
    return T_(entry)


# ─── Font Yöneticisi ─────────────────────────────────────────────
class FontManager:
    """Dile göre font seçer.

    assets/fonts içindeki ortaçağ fontları (Cinzel, MedievalSharp) yalnızca
    Latin alfabesini kapsıyor; Kiril ve Arap harflerini çizemiyorlar. Bu
    yüzden her dil için aday listesi ayrı ve seçilen font o dilin alfabesini
    gerçekten çizebiliyor mu diye sınanıyor.
    """
    _cache:Dict={}
    _lang="TR"
    FONT_DIR = os.path.join(ASSET_DIR,"assets","fonts")

    # Dilin gerektirdiği harfler — font bunları çizemiyorsa elenir.
    PROBES = {
        "TR":"ğĞşŞıİçÇöÖüÜ",
        "EN":"ABCabc",
        "DE":"äöüßÄÖÜ",
        "RU":"ЁЙЩЪЫЭЮЯёйщъыэюя",
        "AR":"تجالظمبسنقر",
    }
    # Sıra: önce oyunun kendi ortaçağ fontu, sonra sistem fontları.
    CANDIDATES = {
        "title": ["Cinzel-Bold.ttf","Cinzel-Regular.ttf"],
        "dialog":["MedievalSharp-Regular.ttf"],
        "deco":  ["MedievalSharp-Regular.ttf"],
        "mono":  [],   # hizali bilgi (HUD sayilari) — sistem fontundan
    }
    # "mono" stili icin ayri liste: once dar/sabit genislikli fontlar
    MONO_FALLBACK = {
        "TR":["consolas","couriernew","monospace"],
        "EN":["consolas","couriernew","monospace"],
        "DE":["consolas","couriernew","monospace"],
        "RU":["consolas","couriernew","tahoma","segoeui"],
        "AR":["tahoma","segoeui","arial"],
    }
    SYSTEM_FALLBACK = {
        "TR":["georgia","times new roman","palatino","serif"],
        "EN":["georgia","times new roman","palatino","serif"],
        "DE":["georgia","times new roman","palatino","serif"],
        "RU":["georgia","times new roman","tahoma","segoeui","serif"],
        "AR":["tahoma","segoeui","arial","serif"],
    }

    @classmethod
    def set_language(cls,code):
        if code!=cls._lang:
            cls._lang=code
            cls._cache.clear()

    # Hiçbir fontta bulunmayan bir kod noktası: "eksik glif" görüntüsünün örneği
    _NOTDEF_CHAR = ""

    @classmethod
    def _renders(cls,font,probe)->bool:
        """Font bu harfleri gerçekten çiziyor mu?

        Üç ölçüm de yanıltıyor, sırayla öğrenildi:
          * font.metrics() eksik glif için de değer döndürüyor,
          * genişlik ölçümü de (glif yer ayırıyor ama çizmiyor),
          * "hiç piksel yok" ölçütü Almendra'yı yakalıyor ama Cinzel'i
            kaçırıyor — Cinzel eksik harfi BOŞ değil KUTU olarak çiziyor.
        Bu yüzden her harfin görüntüsü, kesinlikle eksik olan bir kod
        noktasının görüntüsüyle karşılaştırılıyor.
        """
        try:
            def shot(ch):
                s=font.render(ch,True,WH)
                return (s.get_width(),pygame.image.tostring(s,"RGBA"))
            notdef=shot(cls._NOTDEF_CHAR)
            for ch in probe:
                cur=shot(ch)
                if cur==notdef: return False          # eksik glif kutusu
                if not pygame.mask.from_surface(font.render(ch,True,WH)).count():
                    return False                       # hiç çizilmiyor
            return True
        except Exception:
            return False

    @classmethod
    def _find(cls,style,size):
        probe=cls.PROBES.get(cls._lang,cls.PROBES["EN"])
        for name in cls.CANDIDATES.get(style,cls.CANDIDATES["title"]):
            path=os.path.join(cls.FONT_DIR,name)
            if os.path.exists(path):
                try:
                    f=pygame.font.Font(path,size)
                    if cls._renders(f,probe): return f
                except Exception: pass
        table=cls.MONO_FALLBACK if style=="mono" else cls.SYSTEM_FALLBACK
        for sf in table.get(cls._lang,table["EN"]):
            try:
                f=pygame.font.SysFont(sf,size,bold=True)
                if f and cls._renders(f,probe): return f
            except Exception: pass
        return pygame.font.SysFont("monospace",size,bold=True)

    @classmethod
    def get(cls,style:str,size:int)->pygame.font.Font:
        key=(cls._lang,style,size)
        if key in cls._cache: return cls._cache[key]
        f=cls._find(style if style in cls.CANDIDATES else "title",size)
        cls._cache[key]=f;return f

# ─── Ses Yöneticisi (Prosedürel ses üretimi — numpy) ─────────────
class SoundManager:
    _sounds:Dict={}
    _enabled=True
    SR=22050  # sample rate

    @classmethod
    def _make(cls,freq,dur,wave="sine",attack=0.01,decay=0.1,vol=0.4,vibrato=0.0,noise=0.0):
        """Prosedürel ses oluştur."""
        try:
            import numpy as np
            n=int(cls.SR*dur); t=np.linspace(0,dur,n,dtype=np.float32)
            if wave=="sine":     w=np.sin(2*np.pi*freq*t)
            elif wave=="square": w=np.sign(np.sin(2*np.pi*freq*t))*0.5
            elif wave=="saw":    w=2*(t*freq-np.floor(t*freq+0.5))
            elif wave=="tri":    w=2*np.abs(2*(t*freq-np.floor(t*freq+0.5)))-1
            else:                w=np.sin(2*np.pi*freq*t)
            if vibrato>0: w*=np.sin(2*np.pi*vibrato*t)*0.1+0.9
            if noise>0:   w+=np.random.uniform(-noise,noise,n)
            env=np.ones(n,dtype=np.float32)
            att=int(cls.SR*attack); dec=int(cls.SR*decay)
            if att>0: env[:min(att,n)]=np.linspace(0,1,min(att,n))
            if dec>0 and att+dec<n:
                env[att:att+dec]=np.linspace(1,0,dec)
                env[att+dec:]=0
            elif dec>0:
                env[att:]=np.linspace(1,0,n-att)
            w=w*env*vol
            w=np.clip(w,-1,1)
            pcm=(w*32767).astype(np.int16)
            stereo=np.column_stack([pcm,pcm])
            return pygame.sndarray.make_sound(stereo)
        except Exception: return None

    @classmethod
    def _chord(cls,freqs,dur,**kw):
        try:
            import numpy as np
            n=int(cls.SR*dur); combined=np.zeros(n,dtype=np.float32)
            for freq in freqs:
                t=np.linspace(0,dur,n,dtype=np.float32)
                combined+=np.sin(2*np.pi*freq*t)
            combined/=len(freqs); combined=np.clip(combined,-1,1)
            pcm=(combined*kw.get("vol",0.35)*32767).astype(np.int16)
            stereo=np.column_stack([pcm,pcm])
            return pygame.sndarray.make_sound(stereo)
        except Exception: return None

    @classmethod
    def init(cls):
        try:
            pygame.mixer.init(frequency=cls.SR,size=-16,channels=2,buffer=512)
        except Exception: cls._enabled=False; return
        defs={
            "hit":      lambda: cls._make(220,0.12,"saw",0.005,0.11,0.5,noise=0.3),
            "hit_heavy":lambda: cls._make(150,0.20,"saw",0.005,0.18,0.6,noise=0.4),
            "heal":     lambda: cls._chord([523,659,784],0.35,vol=0.4),
            "level_up": lambda: cls._chord([261,329,392,523,659,784],0.9,vol=0.5),
            "chest":    lambda: cls._chord([392,494,587,784],0.5,vol=0.4),
            "walk":     lambda: cls._make(80,0.04,"noise",0.001,0.035,0.15,noise=0.8),
            "spell":    lambda: cls._chord([440,554,659],0.25,vol=0.45),
            "arrow":    lambda: cls._make(600,0.10,"saw",0.001,0.09,0.3,noise=0.1),
            "menu_sel": lambda: cls._make(660,0.08,"sine",0.005,0.07,0.3),
            "menu_back":lambda: cls._make(440,0.08,"sine",0.005,0.07,0.25),
            "boss_alert":lambda: cls._chord([110,138,165],0.8,vol=0.55),
            "victory":  lambda: cls._chord([523,659,784,1046],1.2,vol=0.5),
            "death":    lambda: cls._chord([110,138],0.8,vol=0.45),
            "equip":    lambda: cls._chord([330,415,494],0.25,vol=0.35),
            "error":    lambda: cls._make(180,0.18,"square",0.005,0.15,0.3),
            "open_ui":  lambda: cls._chord([392,494,587],0.18,vol=0.3),
            "trap":     lambda: cls._make(330,0.15,"square",0.005,0.12,0.4,noise=0.2),
            "freeze":   lambda: cls._chord([880,1108,1318],0.3,vol=0.35),
        }
        for k,fn in defs.items():
            try:
                s=fn()
                if s: cls._sounds[k]=s
            except Exception: pass

    @classmethod
    def play(cls,name:str):
        if not cls._enabled: return
        s=cls._sounds.get(name)
        if not s: return
        vol=CFG.data.get("master_vol",80)*CFG.data.get("sfx_vol",80)/8000.0
        try: s.set_volume(min(1.0,vol)); s.play()
        except Exception: pass

    # Ambiyans müziği için basit loop thread
    _music_thread = None
    _music_stop   = False
    _music_channel = None
    _music_theme  = None

    _music_cache:Dict={}   # tema → üretilmiş Sound (her geçişte yeniden üretilmesin)

    @classmethod
    def play_music(cls, theme:str="village"):
        """Prosedürel ambient müzik loop — ayrı kanalda.

        Üretilen parça önbelleğe alınır: harita geçişinde numpy ile yeniden
        sentezlemek kareyi takılmaya zorluyordu.
        """
        if not cls._enabled: return
        # Aynı tema zaten çalıyorsa bölme (köy → çayır geçişinde müzik sıfırlanmasın)
        if cls._music_theme==theme and cls._music_channel is not None: return
        cached=cls._music_cache.get(theme)
        if cached is not None:
            try:
                cls.stop_music()
                mv=CFG.data.get("master_vol",80)*CFG.data.get("music_vol",60)/10000.0
                cached.set_volume(min(1.0,mv))
                cls._music_channel=cached.play(loops=-1)
                cls._music_theme=theme
                return
            except Exception: pass
        try:
            import numpy as np, threading
            sr = cls.SR
            # Her temaya özel nota dizisi ve süre
            themes = {
                "village":   ([261,329,392,261,329,392,440,392], 0.30, "sine",  0.18),
                "forest":    ([196,220,247,196,220,261,220,196], 0.40, "sine",  0.14),
                "dungeon":   ([110,123,138,110,123,110,103,110], 0.50, "tri",   0.12),
                "battle":    ([196,220,165,196,247,220,196,165], 0.22, "square",0.10),
                "castle":    ([138,155,174,138,155,130,138,174], 0.45, "saw",   0.09),
                "victory":   ([523,659,784,659,523,659,784,880], 0.20, "sine",  0.20),
                "library":   ([220,247,277,247,220,196,220,247], 0.45, "sine",  0.13),
            }
            if theme not in themes: theme = "village"
            notes, dur, wave, vol = themes[theme]
            # Ses parçalarını oluştur
            segs = []
            for freq in notes:
                n = int(sr*dur)
                t = np.linspace(0, dur, n, dtype=np.float32)
                if wave=="sine":   w = np.sin(2*np.pi*freq*t)
                elif wave=="tri":  w = 2*np.abs(2*(t*freq - np.floor(t*freq+0.5)))-1
                elif wave=="square": w = np.sign(np.sin(2*np.pi*freq*t))*0.5
                else:              w = 2*(t*freq - np.floor(t*freq+0.5))
                # Zarif giriş/çıkış
                fade = min(int(sr*0.06), n//4)
                env  = np.ones(n, dtype=np.float32)
                env[:fade]  = np.linspace(0,1,fade)
                env[-fade:] = np.linspace(1,0,fade)
                w = w * env * vol
                segs.append(w)
            loop = np.concatenate(segs).astype(np.float32)
            loop = np.clip(loop, -1, 1)
            pcm  = (loop * 32767).astype(np.int16)
            stereo = np.column_stack([pcm, pcm])
            snd = pygame.sndarray.make_sound(stereo)
            cls._music_cache[theme] = snd
            # Mevcut müziği durdur
            cls.stop_music()
            mv = CFG.data.get("master_vol",80) * CFG.data.get("music_vol",60) / 10000.0
            snd.set_volume(min(1.0, mv))
            cls._music_channel = snd.play(loops=-1)
            cls._music_theme = theme
        except Exception as e:
            pass  # Sessizce geç

    @classmethod
    def stop_music(cls):
        try:
            if cls._music_channel:
                cls._music_channel.stop()
                cls._music_channel = None
                cls._music_theme = None
        except Exception: pass

    @classmethod
    def update_music_volume(cls):
        try:
            if cls._music_channel:
                mv = CFG.data.get("master_vol",80) * CFG.data.get("music_vol",60) / 10000.0
                cls._music_channel.set_volume(min(1.0, mv))
        except Exception: pass

    @classmethod
    def set_volume(cls,master:int,sfx:int):
        cls.update_music_volume()

# ─── Renkler ────────────────────────────────────────────────────
BK=(0,0,0);WH=(255,255,255);DKG=(14,8,22)
GR=(72,78,90);LGR=(150,158,170)
G_D=(34,85,34);G_L=(56,118,56)
DT=(101,67,33);DT_L=(139,90,43)
ST=(82,82,94);ST_L=(112,112,124)
WD_=(20,55,115);WD_L=(35,85,170)
SD=(185,158,98);SN=(182,203,222);SN_L=(222,236,246);IC=(98,158,198)
SHT=(33,16,52);SHL=(58,28,85)
WOD=(112,72,32);WL=(168,148,120);FL=(56,42,32)
CAC=(60,140,60);FARM_D=(90,120,40);RIV=(30,100,180)
UI_BG=(12,6,24);UI_BD=(105,65,172);UI_TX=(226,216,250)
UI_AC=(168,108,250);UI_GD=(230,180,40);UI_GN=(40,178,75)
UI_RD=(205,40,40);UI_BL=(40,95,215);UI_CY=(40,195,205);UI_PR=(140,60,200)
HP_R=(196,36,36);HP_G=(36,176,56);MP_B=(46,115,225);XP_T=(46,205,175)
CLASS_COL={"warrior":(192,72,52),"mage":(92,72,212),"archer":(52,172,72),"healer":(212,172,52)}
CLASS_INFO={
    "warrior":{"name":"Savasci","desc":"Guclu yakın dovuscu.","lore":"Demirden yumruklar,\ncelik kalp.",
               "bonus":{"str":3,"vit":3,"agi":1},
               "atk_name":"Kılıç Vuruşu","atk_desc":"Yakin koni saldırı, ekstra krit şansı"},
    "mage":   {"name":"Buyucu","desc":"Guclu buyu kullanicisi.","lore":"Arcane gucu,\nsonsuz tehlike.",
               "bonus":{"int":4,"wis":2,"agi":1},
               "atk_name":"Arcane Boltu","atk_desc":"Oto-nişan büyü mermisi atar"},
    "archer": {"name":"Okcu","desc":"Hizli ve cevik.","lore":"Isabetle atar,\ngolge gibi kayar.",
               "bonus":{"agi":4,"str":2,"vit":1},
               "atk_name":"Hassas Ok","atk_desc":"Baktığı yönde ok atar, krit şansı yüksek"},
    "healer": {"name":"Sifaci","desc":"Destek ve yasam.","lore":"Isik buyusu,\numudun son kalesi.",
               "bonus":{"wis":4,"vit":2,"int":1},
               "atk_name":"Kutsal Darbe","atk_desc":"Yakın kutsal saldırı + hafif iyileşme"},
}

# ─── Ekipman Sistemi ────────────────────────────────────────────
EQUIP_ITEMS = {
    # Silahlar
    "iron_sword":   ("Demir Kılıç",  HP_R,   {"str":4},          "weapon",    {"warrior"}),
    "steel_sword":  ("Celik Kılıç",  ST_L,   {"str":6,"vit":1},  "weapon",    {"warrior"}),
    "fine_bow":     ("Ince Yay",     G_L,    {"agi":3,"str":1},  "weapon",    {"archer"}),
    "shadow_bow":   ("Golge Yay",    SHT,    {"agi":5,"str":2},  "weapon",    {"archer"}),
    "arcane_staff": ("Arcane Asa",   UI_PR,  {"int":4},          "weapon",    {"mage"}),
    "elder_staff":  ("Yaşlı Asa",    UI_BD,  {"int":6,"wis":1},  "weapon",    {"mage"}),
    "holy_scepter": ("Kutsal Asa",   UI_GD,  {"wis":3,"int":2},  "weapon",    {"healer"}),
    # Zırhlar
    "leather_armor":("Deri Zırh",    DT,     {"vit":2,"agi":1},  "armor",     None),
    "plate_mail":   ("Plaka Zırh",   ST_L,   {"vit":4,"str":1},  "armor",     {"warrior"}),
    "mage_robe":    ("Buyucu Cubbe", UI_BL,  {"int":2,"wis":2},  "armor",     {"mage"}),
    "healer_robe":  ("Sifaci Cubbe", UI_GN,  {"wis":3,"vit":2},  "armor",     {"healer"}),
    "scout_coat":   ("Izci Palto",   G_D,    {"agi":3,"vit":1},  "armor",     {"archer"}),
    # Botlar
    "swift_boots":  ("Hiz Botları",  G_L,    {"agi":3},          "boots",     None),
    # Yüzükler
    "power_ring":   ("Guc Yuzugu",   UI_GD,  {"str":2,"vit":1},  "ring",      None),
    "mage_focus":   ("Odak Kristali",UI_AC,  {"int":3,"wis":1},  "ring",      {"mage"}),
    # Muskalar
    "mana_gem":     ("Mana Tası",    UI_CY,  {"wis":2,"int":1},  "amulet",    None),
    "warrior_crest":("Savasci Nisan",(220,80,40),{"str":2,"vit":2},"amulet",  {"warrior"}),
    "archer_token": ("Nisan Tası",   G_L,    {"agi":2,"str":1},  "amulet",    {"archer"}),
}

# Ekipman yuvalarının sabit sırası — envanter imleci ve çizim bunu paylaşır.
# NOT: Önceden bot, yüzük, muska ve nişanların HEPSİ tek "ring" yuvasındaydı;
# mana taşı takınca hız botu çıkıyordu. Yuvalar türe göre ayrıldı.
EQUIP_SLOTS = ("weapon","armor","boots","ring","amulet")
SLOT_NAMES  = {"weapon":"Silah","armor":"Zirh","boots":"Bot","ring":"Yuzuk","amulet":"Muska"}
SLOT_COLORS = {"weapon":UI_RD,"armor":ST_L,"boots":G_L,"ring":UI_GD,"amulet":UI_CY}

ITEMS = {
    "hp_pot": ("Saglik Iksiri", HP_G,   "heal",   35,  "35 HP iyilestirir."),
    "mp_pot": ("Mana Iksiri",   MP_B,   "mana",   25,  "25 MP iyilestirir."),
    "gold":   ("Altin",         UI_GD,  "gold",    5,  "Degerli para."),
    "earth_c":("Toprak Kristali",(120,200,80),"quest",0,"Antik kristal."),
    "water_c":("Su Kristali",  (80,180,220),"quest",0,"Antik kristal."),
    "farm_tool":("Ciftci Aleti",(140,100,60),"stat_str",1,"STR +1 kalici."),
    "river_gem":("Nehir Tasi", (60,180,200),"stat_wis",1,"WIS +1 kalici."),
    "scroll1":  ("Karanlik Parsomen",(180,140,220),"quest_sq",0,"Gizemli parsomen 1/3."),
    "scroll2":  ("Ates Parsomeni",  (220,140,80), "quest_sq",0,"Gizemli parsomen 2/3."),
    "scroll3":  ("Buz Parsomeni",   (140,200,220),"quest_sq",0,"Gizemli parsomen 3/3."),
}
# Tüm eşyaları birleştir (envanter ve ekipman)
ALL_ITEMS = dict(ITEMS)
for k,(name,col,bonus,slot,cls) in EQUIP_ITEMS.items():
    desc = " / ".join(f"{s.upper()}+{v}" for s,v in bonus.items())
    ALL_ITEMS[k] = (name, col, "equip", slot, desc)

# ─── Yetenek Sistemi ────────────────────────────────────────────
ABILITIES = {
    "warrior":[
        {"id":"shield_bash","name":"Kalkan Darb.","level":1,"mp":6, "cd":50, "col":(220,100,50)},
        {"id":"whirlwind",  "name":"Kasirga",     "level":3,"mp":14,"cd":100,"col":(200,160,60)},
        {"id":"war_cry",    "name":"Savas Ciglik","level":5,"mp":18,"cd":200,"col":(220,60,60)},
        {"id":"earthquake", "name":"Deprem",      "level":8,"mp":28,"cd":320,"col":(180,120,40)},
    ],
    "mage":[
        {"id":"freeze",     "name":"Buz Kilidi",  "level":1,"mp":16,"cd":80, "col":(80,180,255)},
        {"id":"meteor",     "name":"Meteor",      "level":3,"mp":26,"cd":200,"col":(255,80,40)},
        {"id":"arcane_nova","name":"A.Nova",      "level":5,"mp":36,"cd":260,"col":(180,80,255)},
        {"id":"time_stop",  "name":"Zaman Dur.",  "level":8,"mp":48,"cd":400,"col":(200,200,255)},
    ],
    "archer":[
        {"id":"multi_shot", "name":"Coklu Atis",  "level":1,"mp":8, "cd":40, "col":(80,200,80)},
        {"id":"trap",       "name":"Tuzak Kur",   "level":3,"mp":10,"cd":60, "col":(160,120,40)},
        {"id":"rain_arrows","name":"Ok Yagmuru",  "level":5,"mp":22,"cd":180,"col":(60,220,120)},
        {"id":"shadow_step","name":"Golge Adim",  "level":8,"mp":25,"cd":240,"col":(80,60,160)},
    ],
    "healer":[
        {"id":"mass_heal",  "name":"Alan Iyilesme","level":1,"mp":18,"cd":80, "col":(80,220,120)},
        {"id":"holy_shield","name":"K.Kalkan",     "level":3,"mp":20,"cd":120,"col":(255,220,60)},
        {"id":"divine_storm","name":"I.Firtina",   "level":5,"mp":32,"cd":200,"col":(220,200,255)},
        {"id":"resurrection","name":"Dirilis",     "level":8,"mp":50,"cd":500,"col":(255,180,100)},
    ],
}

QUESTS = {
    1:("Kotulugun Uyanisi","Ashveil'de Yasli Aldric ile konus."),
    2:("Ormanin Sirri",    "Karanlik Ormanda Sir Roland'i bul."),
    3:("Toprak Kristali",  "Antik Harabelerde Toprak Kristalini al."),
    4:("Kahin Kehaneti",   "Colde Oracle Nyx'i bul."),
    5:("Buzun Kalbi",      "Buz Magarasinda Su Kristalini al."),
    6:("Son Savas",        "Golge Kalesinde Malachar'i yen!"),
}

# ─── Yan görevler ────────────────────────────────────────────────
# Yeni görev eklemek tek satır: ilerleme fonksiyonu (bulunan, hedef)
# döndürür, tamamlanınca ödül bir kez verilir.
SIDE_QUESTS = [
    {"id":"scroll",  "title":"ui.sq_scroll",  "desc":"ui.sq_scroll_desc",
     "unit":"ui.unit_scroll","col":UI_PR,
     "progress":lambda f: (sum(1 for k in("sq_scroll1","sq_scroll2","sq_scroll3") if f.get(k)),3),
     "gold":80,"xp":60},
    {"id":"boar",    "title":"ui.sq_boar",    "desc":"ui.sq_boar_desc",
     "unit":"ui.unit_boar","col":UI_GD,
     "progress":lambda f: (min(3,f.get("kill_boar",0)),3),
     "gold":50,"xp":40},
    {"id":"fish",    "title":"ui.sq_fish",    "desc":"ui.sq_fish_desc",
     "unit":"ui.unit_talk","col":UI_CY,
     "progress":lambda f: (1 if f.get("sq_fish_done") else 0,1),
     "gold":40,"xp":30},
    {"id":"wolf",    "title":"ui.sq_wolf",    "desc":"ui.sq_wolf_desc",
     "unit":"ui.unit_wolf","col":(190,170,150),
     "progress":lambda f: (min(5,f.get("kill_wolf",0)),5),
     "gold":70,"xp":70},
    {"id":"bone",    "title":"ui.sq_bone",    "desc":"ui.sq_bone_desc",
     "unit":"ui.unit_skeleton","col":(220,220,210),
     "progress":lambda f: (min(6,f.get("kill_skeleton",0)),6),
     "gold":90,"xp":90},
    {"id":"golem",   "title":"ui.sq_golem",   "desc":"ui.sq_golem_desc",
     "unit":"ui.unit_golem","col":(150,140,130),
     "progress":lambda f: (min(2,f.get("kill_golem",0)),2),
     "gold":120,"xp":120},
    {"id":"witch",   "title":"ui.sq_witch",   "desc":"ui.sq_witch_desc",
     "unit":"ui.unit_talk","col":(140,200,140),
     "progress":lambda f: (1 if f.get("sq_witch_done") else 0,1),
     "gold":45,"xp":35},
    {"id":"hermit",  "title":"ui.sq_hermit",  "desc":"ui.sq_hermit_desc",
     "unit":"ui.unit_talk","col":(200,180,220),
     "progress":lambda f: (1 if f.get("sq_hermit_done") else 0,1),
     "gold":45,"xp":35},
]

# Hangi NPC'nin konusulacak bir isi var? (basinda ! rozeti gosterilir)
NPC_MARKS = {
    "npc.yasli_aldric":    lambda f: not f.get("speak_aldric"),
    "npc.oracle_nyx":      lambda f: f.get("earth_crystal") and not f.get("speak_oracle"),
    "npc.balikci_riva":    lambda f: not f.get("sq_fish_done"),
    "npc.bataklik_cadisi": lambda f: not f.get("sq_witch_done"),
    "npc.munzevi":         lambda f: not f.get("sq_hermit_done"),
}

def npc_has_quest(npc_key,flags)->bool:
    fn=NPC_MARKS.get(npc_key)
    return bool(fn and fn(flags))

def sq_done(sq,flags)->bool:
    got,need=sq["progress"](flags)
    return got>=need

STAT_NAMES=[("str","Guc"),("int","Zeka"),("agi","Ceviklik"),("vit","Dayaniklilik"),("wis","Bilgelik")]
STAT_DESCS={"str":"Fiziksel saldiri gucu.","int":"Buyu gucu, mana.",
            "agi":"Hareket hizi, kritik.","vit":"Max HP, savunma.","wis":"Max MP, iyilesme."}
STORY_LINES=[
    ("500 yil once...",(220,190,250)),
    ("Golge Lordu MALACHAR karanligini tum topraklara",WH),
    ("yaydı. Koyler yandi, halklar esir dustu.",WH),(" ",WH),
    ("Dort buyuk kahraman kristallerin gucuyle",(180,230,255)),
    ("Malachar'i Golge Alemine hapsetti.",(180,230,255)),
    ("Dunya yeniden isiga kavustu...",(180,230,255)),(" ",WH),
    ("Ta ki bugune kadar.",(255,200,100)),(" ",WH),
    ("Ashveil koyunde bir sabah gokyuzu kararir.",WH),
    ("Muhur zayifliyor. Malachar yeniden uyanmak uzere...",(255,120,120)),(" ",WH),
    ("Koyun yasli bilgesi seni cagiriyor.",(200,255,200)),
    ("Kader bir kez daha bir kahraman istiyor.",UI_GD),
]

# ─── Tile Tipleri ───────────────────────────────────────────────
class T:
    GRASS=0;DIRT=1;STONE=2;WATER=3;SAND=4;TREE=5;WALL=6;FLOOR=7
    DOOR=8;CHEST=9;STAIRS_UP=10;STAIRS_DN=11;CACTUS=12;SNOW=13
    ICE=14;SHADOW=15;DARK_TREE=16;RUINS_WALL=17;PORTAL=18
    SNOW_TREE=19;FARMLAND=20;WHEAT=21;RIVER=22;BRIDGE=23;FENCE=24

WALKABLE={T.GRASS,T.DIRT,T.SAND,T.SNOW,T.FARMLAND,T.WHEAT,
          T.FLOOR,T.DOOR,T.STAIRS_UP,T.STAIRS_DN,T.PORTAL,T.BRIDGE,T.ICE}

# ─── Pixel Art ──────────────────────────────────────────────────
class PA:
    _c:Dict={}
    @staticmethod
    def tile(k,anim=0):
        ck=(k,anim//8 if k in(T.WATER,T.RIVER) else 0)
        if ck in PA._c: return PA._c[ck]
        s=pygame.Surface((TILE,TILE));rs=random.getstate();random.seed(hash(k)*997);Tp=TILE
        if k==T.GRASS:
            s.fill(G_D)
            for _ in range(10): bx,by=random.randint(0,Tp-2),random.randint(0,Tp-2); pygame.draw.rect(s,G_L,(bx,by,2,3))
        elif k==T.DIRT:
            s.fill(DT)
            for _ in range(8): bx,by=random.randint(1,Tp-3),random.randint(1,Tp-3); pygame.draw.rect(s,DT_L,(bx,by,3,2))
        elif k==T.STONE:
            s.fill(ST)
            for r in range(2):
                for c in range(2):
                    ox=c*16+(r*8%16);oy=r*16
                    pygame.draw.rect(s,ST_L,(ox+1,oy+1,13,13));pygame.draw.rect(s,ST,(ox+1,oy+1,13,13),1)
        elif k==T.WATER:
            phase=(anim%60)/60;s.fill(WD_)
            for wx in range(0,Tp,6):
                wy=int(Tp//2+4*math.sin(phase*math.pi*2+wx*0.4));pygame.draw.rect(s,WD_L,(wx,wy,5,3))
        elif k==T.RIVER:
            phase=(anim%60)/60;s.fill(RIV)
            for wx in range(0,Tp,5):
                wy=int(Tp//2+3*math.sin(phase*math.pi*2+wx*0.5));pygame.draw.rect(s,(50,130,220),(wx,wy,4,2))
            pygame.draw.line(s,(100,180,255),(0,Tp//4),(Tp,Tp//4),1)
        elif k==T.BRIDGE:
            s.fill(WOD)
            for i in range(0,Tp,4): pygame.draw.line(s,(140,100,50),(i,0),(i,Tp),1)
            pygame.draw.rect(s,(90,60,30),(0,0,Tp,4));pygame.draw.rect(s,(90,60,30),(0,Tp-4,Tp,4))
        elif k==T.SAND:
            s.fill(SD)
            for _ in range(6): bx,by=random.randint(1,Tp-3),random.randint(1,Tp-3); pygame.draw.circle(s,(205,185,135),(bx,by),1)
        elif k==T.SNOW:
            s.fill(SN)
            for _ in range(8): bx,by=random.randint(2,Tp-3),random.randint(2,Tp-3); pygame.draw.circle(s,WH,(bx,by),1)
        elif k==T.ICE:
            s.fill(IC)
            for r in range(2):
                for c in range(2):
                    pygame.draw.rect(s,(140,200,235),(c*16+1,r*16+1,13,13));pygame.draw.rect(s,IC,(c*16+1,r*16+1,13,13),1)
            pygame.draw.line(s,(180,225,255),(2,2),(Tp-3,Tp-3),1)
        elif k==T.FARMLAND:
            s.fill(FARM_D)
            for row in range(4): pygame.draw.line(s,(120,160,60),(0,row*8+4),(Tp,row*8+4),2)
        elif k==T.WHEAT:
            s.fill(FARM_D)
            for wx in range(4,Tp-4,5):
                h=random.randint(10,18);pygame.draw.line(s,(200,170,50),(wx,Tp-2),(wx,Tp-2-h),2)
                pygame.draw.ellipse(s,(220,190,60),(wx-3,Tp-2-h-5,6,5))
        elif k==T.TREE:
            s.fill(G_D);pygame.draw.rect(s,WOD,(12,18,8,14))
            pygame.draw.polygon(s,(20,100,20),[(16,2),(4,20),(28,20)])
            pygame.draw.polygon(s,(30,130,30),[(16,6),(6,22),(26,22)])
            pygame.draw.polygon(s,(50,160,50),[(16,10),(8,24),(24,24)])
        elif k==T.DARK_TREE:
            s.fill(SHT);pygame.draw.rect(s,(60,35,20),(12,18,8,14))
            pygame.draw.polygon(s,(20,40,20),[(16,2),(4,20),(28,20)])
            pygame.draw.polygon(s,(15,30,15),[(16,6),(6,22),(26,22)])
            for _ in range(3):
                ex,ey=random.randint(8,24),random.randint(4,20);pygame.draw.circle(s,(180,20,20),(ex,ey),2)
        elif k==T.SNOW_TREE:
            s.fill(SN);pygame.draw.rect(s,WOD,(12,18,8,14))
            pygame.draw.polygon(s,SN_L,[(16,2),(4,20),(28,20)])
            pygame.draw.polygon(s,WH,[(16,6),(6,22),(26,22)])
            pygame.draw.polygon(s,SN_L,[(16,10),(8,24),(24,24)])
        elif k==T.CACTUS:
            s.fill(SD);pygame.draw.rect(s,CAC,(13,8,6,22))
            pygame.draw.rect(s,CAC,(6,12,8,4));pygame.draw.rect(s,CAC,(18,15,8,4))
        elif k==T.WALL:
            s.fill(WL)
            for r in range(4):
                for c in range(2):
                    ox=c*16+(r%2)*8;oy=r*8
                    pygame.draw.rect(s,(195,175,145),(ox+1,oy+1,13,5));pygame.draw.rect(s,(155,135,105),(ox+1,oy+1,13,5),1)
        elif k==T.RUINS_WALL:
            s.fill((70,60,50))
            for r in range(4):
                for c in range(2):
                    ox=c*16+(r%2)*8;oy=r*8
                    col=(90,75,60) if random.random()>0.3 else (65,55,45)
                    pygame.draw.rect(s,col,(ox+1,oy+1,13,5));pygame.draw.rect(s,(50,42,35),(ox+1,oy+1,13,5),1)
        elif k==T.FLOOR:
            s.fill(FL)
            for r in range(2):
                for c in range(2):
                    pygame.draw.rect(s,(70,52,38),(c*16+1,r*16+1,13,13))
                    pygame.draw.line(s,(45,33,23),(c*16+1,r*16+14),(c*16+14,r*16+14),1)
        elif k==T.DOOR:
            s.fill(FL);pygame.draw.rect(s,WOD,(8,0,16,32));pygame.draw.rect(s,(145,95,45),(9,1,14,30))
            pygame.draw.circle(s,UI_GD,(22,16),2)
        elif k==T.CHEST:
            s.fill(G_D);pygame.draw.rect(s,(95,65,28),(6,14,20,14));pygame.draw.rect(s,(135,95,48),(7,15,18,12))
            pygame.draw.rect(s,(95,65,28),(6,10,20,6));pygame.draw.circle(s,UI_GD,(16,20),3)
        elif k==T.SHADOW:
            s.fill(SHT)
            for r in range(4):
                for c in range(2):
                    ox=c*16+(r%2)*8;oy=r*8;pygame.draw.rect(s,SHL,(ox+1,oy+1,13,5))
        elif k in(T.STAIRS_UP,T.STAIRS_DN):
            s.fill(FL)
            for i in range(4):
                c2=(ST[0]+i*8,ST[1]+i*8,ST[2]+i*8);pygame.draw.rect(s,c2,(i*4,8+i*4,32-i*8,6))
                pygame.draw.rect(s,ST_L,(i*4,8+i*4,32-i*8,2))
            col2=UI_GN if k==T.STAIRS_UP else UI_RD
            pts=[(16,4),(10,14),(22,14)] if k==T.STAIRS_UP else [(16,28),(10,18),(22,18)]
            pygame.draw.polygon(s,col2,pts)
        elif k==T.PORTAL:
            s.fill(SHT);pygame.draw.circle(s,UI_BD,(16,16),12,2)
            pygame.draw.circle(s,UI_AC,(16,16),7,2);pygame.draw.circle(s,UI_AC,(16,16),3)
        elif k==T.FENCE:
            s.fill(G_D);pygame.draw.rect(s,WOD,(2,10,28,3))
            pygame.draw.rect(s,WOD,(4,10,3,18));pygame.draw.rect(s,WOD,(25,10,3,18))
        random.setstate(rs)
        if k not in(T.WATER,T.RIVER): PA._c[ck]=s
        return s

    # ── Sprite son işlemleri ─────────────────────────────────────
    # Karakterler zeminde yüzüyormuş gibi duruyordu ve koyu haritalarda
    # arka plandan ayrışmıyorlardı. Üç sistemik ekleme her şeyi birden
    # düzeltiyor: taban gölgesi, koyu kontur ve kare kare animasyon.
    ANIM_FRAMES = 8      # animasyon poz sayısı
    ANIM_HOLD   = 4      # her poz kaç oyun karesi sürer (15 FPS his)
    OUTLINE_COL = (14,9,20)

    @staticmethod
    def anim(frame:int)->int:
        """Sürekli kare sayacını ayrık animasyon pozuna çevirir.

        Hem piksel sanatına yakışan basamaklı hareket veriyor hem de
        sprite'ların önbelleğe alınmasını mümkün kılıyor (sonsuz ara değer
        yerine 8 poz).
        """
        return (frame//PA.ANIM_HOLD)%PA.ANIM_FRAMES

    @staticmethod
    def _bob(af:int,amp:float=1.5)->int:
        return int(math.sin(af/PA.ANIM_FRAMES*math.tau)*amp)

    @staticmethod
    def _finish(src,shadow=True,outline=True):
        """Gölge + kontur ekler. Sonuç aynı boyutta kalır."""
        w,h=src.get_size()
        out=pygame.Surface((w,h),pygame.SRCALPHA)
        if shadow:
            sh=pygame.Surface((w,h),pygame.SRCALPHA)
            pygame.draw.ellipse(sh,(0,0,0,70),(w//2-9,h-7,18,6))
            out.blit(sh,(0,0))
        if outline:
            sil=pygame.mask.from_surface(src).to_surface(
                setcolor=PA.OUTLINE_COL,unsetcolor=(0,0,0,0))
            for dx,dy in((-1,0),(1,0),(0,-1),(0,1)):
                out.blit(sil,(dx,dy))
        out.blit(src,(0,0))
        return out

    @staticmethod
    def player_surf(direction,frame,char_class="warrior"):
        af=PA.anim(frame)
        key=("pl",direction,af,char_class)
        if key in PA._c: return PA._c[key]
        s=PA._player_raw(direction,af,char_class)
        s=PA._finish(s);PA._c[key]=s;return s

    @staticmethod
    def _player_raw(direction,af,char_class="warrior"):
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        frame=af*PA.ANIM_HOLD
        bob=PA._bob(af)
        cc=CLASS_COL.get(char_class,(80,120,220));skin=(200,160,120)
        pygame.draw.rect(s,cc,(10,14+bob,12,12))
        pygame.draw.rect(s,skin,(9,4+bob,14,12))
        ey=7+bob
        if direction in("right","down"): pygame.draw.rect(s,BK,(17,ey,3,3))
        if direction in("left","down"):  pygame.draw.rect(s,BK,(11,ey,3,3))
        if char_class=="warrior":
            pygame.draw.rect(s,(160,40,40),(7,3+bob,18,5));pygame.draw.rect(s,(190,60,60),(5,4+bob,22,3))
        elif char_class=="mage":
            pygame.draw.polygon(s,(60,30,110),[(16,bob-2),(8,6+bob),(24,6+bob)])
            pygame.draw.circle(s,(200,100,255),(16,bob+1),2)
        elif char_class=="archer":
            pygame.draw.rect(s,(40,100,40),(8,3+bob,16,5))
        elif char_class=="healer":
            pygame.draw.rect(s,(200,160,40),(8,3+bob,16,5))
            pygame.draw.rect(s,(255,220,60),(13,1+bob,6,8));pygame.draw.rect(s,(255,220,60),(10,3+bob,12,4))
        lo=int(math.sin(af/PA.ANIM_FRAMES*math.tau)*3)
        lc=(int(cc[0]*0.7),int(cc[1]*0.7),int(cc[2]*0.7))
        pygame.draw.rect(s,lc,(10,26+bob,5,6-abs(lo)//2));pygame.draw.rect(s,lc,(17,26+bob,5,6+abs(lo)//2))
        pygame.draw.rect(s,(35,25,18),(9,31+bob,6,2));pygame.draw.rect(s,(35,25,18),(16,31+bob,6,2))
        sw=int(math.sin(af/PA.ANIM_FRAMES*math.tau)*2)
        pygame.draw.rect(s,skin,(5,15+bob+sw,5,8));pygame.draw.rect(s,skin,(22,15+bob-sw,5,8))
        if char_class=="warrior":
            if direction=="right": pygame.draw.rect(s,ST_L,(27,12+bob,3,12));pygame.draw.rect(s,UI_GD,(24,12+bob,9,2))
            elif direction=="left": pygame.draw.rect(s,ST_L,(2,12+bob,3,12));pygame.draw.rect(s,UI_GD,(0,12+bob,9,2))
            else: pygame.draw.rect(s,ST_L,(24,14+bob,3,10));pygame.draw.rect(s,UI_GD,(21,14+bob,9,2))
        elif char_class=="mage":
            pygame.draw.rect(s,WOD,(26,8+bob,3,20));pygame.draw.circle(s,(180,100,255),(27,7+bob),4)
            pygame.draw.circle(s,WH,(27,6+bob),2)
        elif char_class=="archer":
            pygame.draw.line(s,(100,160,80),(4,10+bob),(4,26+bob),2)
            pygame.draw.line(s,(220,180,120),(26,14+bob),(28,22+bob),1)
        elif char_class=="healer":
            pygame.draw.rect(s,WOD,(26,10+bob,3,18));pygame.draw.rect(s,(255,220,60),(23,13+bob,9,2))
        return s

    @staticmethod
    def npc_surf(color,frame,style="default"):
        af=PA.anim(frame)
        key=("npc",color,af,style)
        if key in PA._c: return PA._c[key]
        s=PA._finish(PA._npc_raw(color,af,style));PA._c[key]=s;return s

    @staticmethod
    def _npc_raw(color,af,style="default"):
        """NPC çizimleri.

        Önceki hâlde hepsi aynı gövdeydi, yalnızca renk değişiyordu; köyde
        kimin kim olduğu anlaşılmıyordu. Her mesleğin artık kendi silueti,
        başlığı ve elindeki nesnesi var.
        """
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        bob=PA._bob(af,1.0);skin=(205,168,128)

        def body(col,head_y=3,bw=16):
            pygame.draw.rect(s,col,((TILE-bw)//2,13+bob,bw,15))
            dark=(max(0,col[0]-35),max(0,col[1]-35),max(0,col[2]-35))
            pygame.draw.rect(s,dark,((TILE-bw)//2,24+bob,bw,4))
            pygame.draw.rect(s,skin,(9,head_y+bob,14,12))
            pygame.draw.rect(s,(170,135,100),(9,head_y+10+bob,14,2))
            pygame.draw.rect(s,BK,(12,head_y+4+bob,3,3))
            pygame.draw.rect(s,BK,(18,head_y+4+bob,3,3))

        def arms(col):
            sw=PA._bob(af,1.0)
            pygame.draw.rect(s,col,(5,15+bob+sw,4,9))
            pygame.draw.rect(s,col,(23,15+bob-sw,4,9))

        if style=="guard":
            body((78,90,112));arms((70,82,104))
            pygame.draw.rect(s,(96,104,126),(7,1+bob,18,6))          # miğfer
            pygame.draw.rect(s,(140,150,175),(15,0+bob,2,4))
            pygame.draw.line(s,WOD,(26,2+bob),(26,30+bob),2)         # mızrak
            pygame.draw.polygon(s,ST_L,[(26,0+bob),(23,5+bob),(29,5+bob)])
            pygame.draw.ellipse(s,(90,100,120),(1,15+bob,8,11))      # kalkan
        elif style=="knight":
            body((92,96,116));arms((80,84,104))
            pygame.draw.rect(s,(112,118,140),(8,0+bob,16,8))
            pygame.draw.rect(s,BK,(10,3+bob,12,3))                   # vizör
            pygame.draw.polygon(s,(200,60,60),[(16,bob-4),(13,bob),(19,bob)])   # tüy
            pygame.draw.line(s,ST_L,(27,8+bob),(27,26+bob),3)
        elif style=="elder":
            body((132,102,162),head_y=4);arms((118,90,148))
            pygame.draw.polygon(s,(76,40,116),[(16,bob-3),(7,7+bob),(25,7+bob)])
            pygame.draw.polygon(s,(235,235,240),[(11,14+bob),(21,14+bob),(16,26+bob)])  # sakal
            pygame.draw.rect(s,WOD,(26,4+bob,3,25))
            pygame.draw.circle(s,(180,100,255),(27,3+bob),4)
            pygame.draw.circle(s,WH,(27,2+bob),2)
        elif style=="oracle":
            body((62,42,102),head_y=4);arms((52,34,86))
            pygame.draw.polygon(s,(42,22,82),[(16,bob-5),(6,8+bob),(26,8+bob)])
            pygame.draw.circle(s,UI_GD,(16,bob-2),3)
            for i in range(3):
                ang=af/PA.ANIM_FRAMES*math.tau+i*2.1
                ex=int(16+9*math.cos(ang));ey=int(17+6*math.sin(ang)+bob)
                if 0<=ex<TILE and 0<=ey<TILE: pygame.draw.circle(s,UI_GD,(ex,ey),1)
        elif style=="farmer":
            body((146,106,64));arms((128,92,54))
            pygame.draw.ellipse(s,(196,168,92),(4,2+bob,24,7))       # hasır şapka
            pygame.draw.ellipse(s,(168,142,74),(10,0+bob,12,6))
            pygame.draw.rect(s,(210,200,180),(12,16+bob,8,10))       # önlük
            pygame.draw.line(s,WOD,(27,6+bob),(27,30+bob),2)         # dirgen
            for px in(24,27,30): pygame.draw.line(s,ST_L,(px,6+bob),(px,1+bob),1)
        elif style=="smith":
            body((122,84,58));arms((104,70,48))
            pygame.draw.rect(s,(60,52,48),(8,2+bob,16,4))            # bandana
            pygame.draw.rect(s,(74,58,44),(11,16+bob,10,11))         # deri önlük
            pygame.draw.rect(s,WOD,(25,16+bob,3,10))                 # çekiç
            pygame.draw.rect(s,(120,120,132),(22,12+bob,9,5))
        elif style=="inn":
            body((186,132,162));arms((166,116,146))
            pygame.draw.rect(s,(240,230,220),(11,16+bob,10,10))      # önlük
            pygame.draw.rect(s,(214,176,110),(24,17+bob,6,7))        # bardak
            pygame.draw.rect(s,(250,240,210),(24,15+bob,6,3))
            pygame.draw.arc(s,(214,176,110),(28,17+bob,5,7),-1.2,1.2,2)
        elif style=="fisher":
            body((96,138,178));arms((82,120,158))
            pygame.draw.ellipse(s,(176,158,120),(5,2+bob,22,6))      # geniş şapka
            pygame.draw.line(s,WOD,(26,4+bob),(29,26+bob),2)         # olta
            pygame.draw.line(s,(210,225,235),(29,10+bob),(31,20+bob),1)
        elif style=="hermit":
            body((150,134,168),head_y=5);arms((132,116,150))
            pygame.draw.polygon(s,(108,96,124),[(16,1+bob),(6,10+bob),(26,10+bob)])  # kukuleta
            pygame.draw.polygon(s,(230,230,235),[(12,16+bob),(20,16+bob),(16,29+bob)])
            pygame.draw.rect(s,WOD,(26,8+bob,2,21))
        elif style=="scholar":
            body((138,102,196));arms((120,86,176))
            pygame.draw.rect(s,(96,64,150),(8,2+bob,16,4))
            pygame.draw.rect(s,(210,190,150),(22,17+bob,8,7))        # kitap
            pygame.draw.rect(s,(150,60,60),(22,17+bob,2,7))
            pygame.draw.line(s,(120,110,90),(24,20+bob),(29,20+bob),1)
        elif style=="child":
            pygame.draw.rect(s,color,(11,19+bob,10,9))               # küçük gövde
            pygame.draw.rect(s,skin,(10,10+bob,12,10))
            pygame.draw.rect(s,BK,(13,14+bob,2,2));pygame.draw.rect(s,BK,(18,14+bob,2,2))
            pygame.draw.rect(s,(120,80,50),(10,9+bob,12,3))
            pygame.draw.rect(s,color,(7,20+bob,3,6));pygame.draw.rect(s,color,(22,20+bob,3,6))
        elif style=="traveler":
            body(color);arms((max(0,color[0]-30),max(0,color[1]-30),max(0,color[2]-30)))
            pygame.draw.rect(s,(120,96,64),(4,14+bob,7,10))          # sırt çantası
            pygame.draw.rect(s,(96,76,50),(4,17+bob,7,2))
            pygame.draw.rect(s,(90,70,50),(8,1+bob,16,4))
            pygame.draw.line(s,WOD,(27,6+bob),(27,30+bob),2)
        elif style=="spirit":
            aa=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*60)+90
            gs=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            pygame.draw.ellipse(gs,(*color,aa),(7,4+bob,18,22))      # yarı saydam gövde
            pygame.draw.ellipse(gs,(255,255,255,aa//2),(11,7+bob,10,8))
            for i in range(3):                                        # dağılan etek
                pygame.draw.ellipse(gs,(*color,aa//2),(6+i*3,24+bob-i,10,6))
            s.blit(gs,(0,0))
            pygame.draw.circle(s,(255,255,255),(13,12+bob),2)
            pygame.draw.circle(s,(255,255,255),(20,12+bob),2)
        else:
            body(color);arms((max(0,color[0]-30),max(0,color[1]-30),max(0,color[2]-30)))
            pygame.draw.rect(s,(110,86,62),(9,2+bob,14,3))           # saç
        return s

    @staticmethod
    def enemy_surf(kind,frame):
        af=PA.anim(frame)
        key=("en",kind,af)
        if key in PA._c: return PA._c[key]
        s=PA._finish(PA._enemy_raw(kind,af),shadow=(kind!="malachar"))
        PA._c[key]=s;return s

    @staticmethod
    def _enemy_raw(kind,af):
        """Düşman çizimleri.

        Önceki hâlde kurt, domuz ve akrep neredeyse aynı kahverengi
        lekelerdi. Her tür artık ayrı bir siluete sahip: dört ayaklılar
        yandan (baş solda), dik duranlar önden çiziliyor.
        """
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        bob=PA._bob(af,2.0)
        step=PA._bob(af,3.0)          # yürüyen bacaklar

        def beast(body,light,dark,eye,ear="pointed",tusk=False,frost=False):
            """Dört ayaklı gövde — baş solda, kuyruk sağda."""
            for lx,ph in ((9,1),(14,-1),(20,1),(25,-1)):
                pygame.draw.rect(s,dark,(lx,24+bob,4,6+ph*step//2))
            pygame.draw.ellipse(s,body,(7,13+bob,22,13))      # gövde
            pygame.draw.ellipse(s,light,(9,12+bob,15,8))      # sırt ışığı
            pygame.draw.ellipse(s,body,(2,11+bob,13,11))      # kafa
            pygame.draw.ellipse(s,light,(4,12+bob,8,6))
            if ear=="pointed":
                pygame.draw.polygon(s,dark,[(5,11+bob),(3,4+bob),(9,9+bob)])
                pygame.draw.polygon(s,dark,[(12,10+bob),(13,4+bob),(16,10+bob)])
            else:
                pygame.draw.ellipse(s,dark,(3,9+bob,6,5))
                pygame.draw.ellipse(s,dark,(11,8+bob,6,5))
            pygame.draw.ellipse(s,dark,(0,16+bob,6,5))        # burun
            pygame.draw.circle(s,eye,(6,15+bob),2)
            pygame.draw.circle(s,BK,(6,15+bob),1)
            if tusk:
                pygame.draw.polygon(s,(240,235,215),[(2,18+bob),(0,13+bob),(4,16+bob)])
                pygame.draw.polygon(s,(240,235,215),[(6,19+bob),(5,14+bob),(8,17+bob)])
            pygame.draw.polygon(s,dark,[(28,16+bob),(32,10+bob-step),(29,19+bob)])
            if frost:
                for fx,fy in((12,11),(18,12),(23,14)):
                    pygame.draw.polygon(s,(225,250,255),
                                        [(fx,fy+bob-3),(fx-2,fy+bob+1),(fx+2,fy+bob+1)])

        if kind=="slime":
            sq=abs(PA._bob(af,2.0))
            pygame.draw.ellipse(s,(45,155,45),(4-sq//2,16+sq,24+sq,14-sq))
            pygame.draw.ellipse(s,(75,205,75),(6-sq//2,13+sq,20+sq,14-sq))
            pygame.draw.ellipse(s,(150,240,150),(10,15+sq,7,4))
            pygame.draw.circle(s,BK,(12,20+sq),3);pygame.draw.circle(s,BK,(21,20+sq),3)
            pygame.draw.circle(s,WH,(13,19+sq),1);pygame.draw.circle(s,WH,(22,19+sq),1)
        elif kind=="skeleton":
            pygame.draw.line(s,(225,225,215),(16,15+bob),(16,25+bob),2)
            for y in range(16,26,3):
                pygame.draw.line(s,(210,210,200),(11,y+bob),(21,y+bob),2)
            pygame.draw.ellipse(s,(235,235,225),(9,3+bob,14,13))
            pygame.draw.rect(s,BK,(11,7+bob,4,5));pygame.draw.rect(s,BK,(17,7+bob,4,5))
            pygame.draw.rect(s,(255,60,60),(12,8+bob,2,2));pygame.draw.rect(s,(255,60,60),(18,8+bob,2,2))
            for tx in range(12,21,3): pygame.draw.rect(s,(235,235,225),(tx,14+bob,2,2))
            pygame.draw.line(s,(225,225,215),(12,26+bob),(10,31+bob+step),2)
            pygame.draw.line(s,(225,225,215),(20,26+bob),(22,31+bob-step),2)
            pygame.draw.line(s,ST_L,(27,12+bob),(27,26+bob),3)
            pygame.draw.line(s,UI_GD,(24,15+bob),(30,15+bob),2)
        elif kind=="goblin":
            pygame.draw.rect(s,(70,125,52),(10,17+bob,13,11))
            pygame.draw.rect(s,(88,148,62),(11,18+bob,11,5))
            for lx in (10,18): pygame.draw.rect(s,(60,110,45),(lx,27+bob,5,4))
            pygame.draw.ellipse(s,(98,158,68),(7,4+bob,18,15))
            pygame.draw.polygon(s,(88,148,62),[(7,8+bob),(0,4+bob),(8,14+bob)])
            pygame.draw.polygon(s,(88,148,62),[(24,8+bob),(31,4+bob),(23,14+bob)])
            pygame.draw.circle(s,(235,215,70),(12,10+bob),3);pygame.draw.circle(s,(235,215,70),(21,10+bob),3)
            pygame.draw.circle(s,BK,(12,10+bob),1);pygame.draw.circle(s,BK,(21,10+bob),1)
            pygame.draw.line(s,BK,(12,15+bob),(21,15+bob),1)
            for gx in range(13,21,3): pygame.draw.rect(s,WH,(gx,15+bob,2,2))
            pygame.draw.rect(s,WOD,(25,13+bob,3,15))
            pygame.draw.circle(s,(120,120,130),(26,12+bob),4)
        elif kind=="wolf":
            beast((92,84,74),(118,110,98),(64,58,50),(235,200,60))
        elif kind=="ice_wolf":
            beast((120,175,220),(170,215,245),(85,140,190),(200,245,255),frost=True)
        elif kind=="boar":
            beast((128,80,58),(158,104,74),(96,58,40),(230,70,60),ear="round",tusk=True)
        elif kind=="golem":
            pygame.draw.rect(s,(70,66,60),(3,14+bob,7,12))
            pygame.draw.rect(s,(70,66,60),(22,14+bob,7,12))
            pygame.draw.rect(s,(88,84,78),(7,6+bob,18,22))
            pygame.draw.rect(s,(108,104,96),(9,8+bob,14,10))
            pygame.draw.rect(s,(62,58,54),(9,25+bob,5,6))
            pygame.draw.rect(s,(62,58,54),(18,25+bob,5,6))
            for a,b2 in(((10,20),(15,26)),((17,19),(22,24)),((12,9),(16,14))):
                pygame.draw.line(s,(58,54,50),(a[0],a[1]+bob),(b2[0],b2[1]+bob),1)
            glow=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*90)+120
            pygame.draw.circle(s,(glow,90,35),(12,13+bob),3);pygame.draw.circle(s,(glow,90,35),(20,13+bob),3)
            pygame.draw.circle(s,(255,200,110),(12,13+bob),1);pygame.draw.circle(s,(255,200,110),(20,13+bob),1)
        elif kind=="scorpion":
            for lx in (8,13,19): pygame.draw.line(s,(140,84,36),(lx,24+bob),(lx-3,29+bob),2)
            for lx in (12,18,23): pygame.draw.line(s,(140,84,36),(lx,24+bob),(lx+3,29+bob),2)
            pygame.draw.ellipse(s,(172,112,48),(8,17+bob,17,9))
            for i in range(3):
                pygame.draw.circle(s,(186,126,58),(23+i*3,15+bob-i*4),3)
            pygame.draw.circle(s,(206,146,68),(30,5+bob),3)
            pygame.draw.polygon(s,(240,80,70),[(30,1+bob),(28,5+bob),(32,5+bob)])
            for cy,cd in((17,-1),(23,1)):
                pygame.draw.line(s,(160,100,44),(9,cy+bob),(4,cy+cd*3+bob),2)
                pygame.draw.circle(s,(186,126,58),(3,cy+cd*3+bob),3)
            pygame.draw.circle(s,(255,70,60),(13,18+bob),2);pygame.draw.circle(s,(255,70,60),(19,18+bob),2)
        elif kind=="shadow_knight":
            aa=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*45)+25
            asurf=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            pygame.draw.circle(asurf,(105,0,160,aa),(16,16),15);s.blit(asurf,(0,0))
            pygame.draw.polygon(s,(32,16,52),[(6,14+bob),(26,14+bob),(29,30+bob),(3,30+bob)])
            pygame.draw.rect(s,(52,28,80),(10,13+bob,12,15))
            pygame.draw.rect(s,(70,40,105),(12,15+bob,8,5))
            pygame.draw.polygon(s,(46,24,72),[(9,10+bob),(23,10+bob),(21,3+bob),(11,3+bob)])
            pygame.draw.polygon(s,(80,45,115),[(9,4+bob),(6,bob),(12,2+bob)])
            pygame.draw.polygon(s,(80,45,115),[(23,4+bob),(26,bob),(20,2+bob)])
            glow2=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*150)+90
            pygame.draw.rect(s,(glow2,0,glow2//2),(11,6+bob,10,3))
            pygame.draw.rect(s,(60,35,90),(26,9+bob,3,19))
            pygame.draw.rect(s,(150,70,200),(24,12+bob,7,2))
        elif kind=="malachar":
            sc=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA);b2=PA._bob(af,3.0)
            aa2=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*80)+40
            as2=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA)
            pygame.draw.circle(as2,(120,0,180,aa2),(32,32),30);sc.blit(as2,(0,0))
            pygame.draw.polygon(sc,(18,7,32),[(8,24+b2),(56,24+b2),(60,62+b2),(4,62+b2)])
            pygame.draw.rect(sc,(35,15,60),(16,22+b2,32,40))
            pygame.draw.rect(sc,(52,24,86),(20,26+b2,24,14))
            pygame.draw.ellipse(sc,(26,10,46),(14,4+b2,36,24))
            pygame.draw.polygon(sc,(70,28,96),[(20,8+b2),(12,b2-6),(18,12+b2)])
            pygame.draw.polygon(sc,(70,28,96),[(44,8+b2),(52,b2-6),(46,12+b2)])
            gm=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*170)+70
            pygame.draw.circle(sc,(gm,0,gm//2),(23,16+b2),6);pygame.draw.circle(sc,(gm,0,gm//2),(41,16+b2),6)
            pygame.draw.circle(sc,(255,160,210),(23,16+b2),2);pygame.draw.circle(sc,(255,160,210),(41,16+b2),2)
            pygame.draw.rect(sc,(58,26,86),(15,2+b2,34,7))
            for ti in range(0,34,6):
                pygame.draw.polygon(sc,UI_BD,[(16+ti,2+b2),(19+ti,-4+b2),(22+ti,2+b2)])
            return sc
        return s

    @staticmethod
    def proj_surf(kind,frame):
        s=pygame.Surface((18,18),pygame.SRCALPHA)
        if kind=="arrow":
            pygame.draw.line(s,(180,140,60),(2,9),(15,9),2)
            pygame.draw.polygon(s,(220,180,80),[(15,6),(15,12),(18,9)])
            pygame.draw.line(s,(200,160,70),(2,8),(5,7),1);pygame.draw.line(s,(200,160,70),(2,10),(5,11),1)
        elif kind=="fireball":
            glow=int(abs(math.sin(frame*0.15))*40)+180
            pygame.draw.circle(s,(glow,80,20),(9,9),7);pygame.draw.circle(s,(255,160,40),(9,9),5)
            pygame.draw.circle(s,(255,220,100),(9,9),3)
            for i in range(5):
                ang=frame*0.2+i*1.26;ex=int(9+10*math.cos(ang));ey=int(9+10*math.sin(ang))
                if 0<=ex<18 and 0<=ey<18: pygame.draw.circle(s,(255,100,0),(ex,ey),2)
        elif kind=="arcane_bolt":
            glow=int(abs(math.sin(frame*0.18))*60)+160
            pygame.draw.circle(s,(glow//2,40,glow),(9,9),7);pygame.draw.circle(s,(140,80,255),(9,9),4)
            pygame.draw.circle(s,WH,(9,9),2)
        elif kind=="ice_bolt":
            pygame.draw.polygon(s,(80,180,255),[(9,0),(13,9),(9,18),(5,9)])
            pygame.draw.polygon(s,(180,230,255),[(9,3),(12,9),(9,15),(6,9)]);pygame.draw.circle(s,WH,(9,9),2)
        elif kind=="holy_bolt":
            glow=int(abs(math.sin(frame*0.2))*50)+180
            pygame.draw.circle(s,(255,glow,60),(9,9),7);pygame.draw.circle(s,(255,240,120),(9,9),4)
            pygame.draw.circle(s,WH,(9,9),2)
            for i in range(4):
                ang=frame*0.15+i*1.57;ex=int(9+7*math.cos(ang));ey=int(9+7*math.sin(ang))
                if 0<=ex<18 and 0<=ey<18: pygame.draw.circle(s,(255,220,80),(ex,ey),1)
        elif kind=="shadow_bolt":
            pygame.draw.circle(s,(80,0,120),(9,9),7);pygame.draw.circle(s,(140,40,200),(9,9),4)
            pygame.draw.circle(s,(200,100,255),(9,9),2)
        return s

    @staticmethod
    def hit_fx_surf(frame,max_f):
        s=pygame.Surface((48,48),pygame.SRCALPHA);tt=frame/max_f;r=int(24*tt);a=int(255*(1-tt))
        pygame.draw.circle(s,(*HP_R,a),(24,24),max(1,r))
        for ang in range(0,360,45):
            rad=math.radians(ang);ex=int(24+r*math.cos(rad));ey=int(24+r*math.sin(rad))
            pygame.draw.circle(s,(255,200,50,a),(ex,ey),2)
        return s

    @staticmethod
    def trap_surf(triggered):
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        if not triggered:
            pygame.draw.ellipse(s,(100,80,40),(4,12,24,8));pygame.draw.ellipse(s,(140,110,60),(5,13,22,6))
            pygame.draw.line(s,(80,60,30),(8,16),(24,16),2)
        else:
            pygame.draw.line(s,(220,100,30),(4,4),(28,28),3);pygame.draw.line(s,(220,100,30),(28,4),(4,28),3)
            pygame.draw.circle(s,(255,200,50),(16,16),5,2)
        return s

    @staticmethod
    def prop_surf(kind):
        """Yürümeyi engellemeyen dekor: harita boşluğunu doldurur."""
        key=("prop",kind)
        if key in PA._c: return PA._c[key]
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        if kind=="flower":
            for(fx,fy,c) in((10,18,(230,220,90)),(20,22,(220,130,190)),(15,14,(150,200,230))):
                pygame.draw.line(s,(60,120,60),(fx,fy+5),(fx,fy+1))
                pygame.draw.circle(s,c,(fx,fy),2)
        elif kind=="rock":
            pygame.draw.ellipse(s,(90,92,100),(8,16,16,10))
            pygame.draw.ellipse(s,(122,124,134),(10,15,11,7))
        elif kind=="bush":
            pygame.draw.circle(s,(34,78,38),(16,20),8)
            pygame.draw.circle(s,(48,104,50),(13,18),5)
            pygame.draw.circle(s,(48,104,50),(20,20),4)
        elif kind=="stump":
            pygame.draw.rect(s,(92,64,38),(11,16,10,9))
            pygame.draw.ellipse(s,(132,96,58),(10,13,12,6))
        elif kind=="mushroom":
            pygame.draw.rect(s,(220,210,190),(15,19,3,5))
            pygame.draw.ellipse(s,(180,60,50),(11,14,11,6))
        elif kind=="grasstuft":
            for gx in(11,16,21):
                pygame.draw.line(s,(60,130,62),(gx,24),(gx-2,17))
                pygame.draw.line(s,(78,156,78),(gx,24),(gx+2,18))
        elif kind=="bone":
            pygame.draw.line(s,(210,205,190),(11,20),(21,20),2)
            pygame.draw.circle(s,(210,205,190),(11,20),2);pygame.draw.circle(s,(210,205,190),(21,20),2)
        elif kind=="crystal":
            pygame.draw.polygon(s,(120,190,230),((16,10),(21,20),(16,25),(11,20)))
            pygame.draw.polygon(s,(190,230,255),((16,12),(19,20),(16,22),(14,20)))
        PA._c[key]=s;return s

    @staticmethod
    def equip_icon(slot,col):
        s=pygame.Surface((36,36),pygame.SRCALPHA)
        if slot=="weapon":
            pygame.draw.line(s,col,(8,28),(28,8),3);pygame.draw.polygon(s,col,[(28,8),(22,10),(26,14)])
            pygame.draw.rect(s,(150,120,80),(6,26,6,6))
        elif slot=="armor":
            pygame.draw.polygon(s,col,[(18,4),(6,10),(6,28),(18,32),(30,28),(30,10)])
            pygame.draw.polygon(s,(min(255,col[0]+40),min(255,col[1]+40),min(255,col[2]+40)),[(18,8),(10,13),(10,26),(18,29),(26,26),(26,13)])
        elif slot=="ring":
            pygame.draw.circle(s,col,(18,18),13,3);pygame.draw.circle(s,(200,200,200),(18,18),5,2)
            pygame.draw.circle(s,(220,220,255),(18,18),3)
        elif slot=="boots":
            pygame.draw.polygon(s,col,[(9,10),(17,10),(17,24),(28,24),(28,30),(9,30)])
            pygame.draw.rect(s,(70,55,40),(9,27,19,4))
            pygame.draw.line(s,(240,240,240),(11,14),(15,14),2)
        elif slot=="amulet":
            pygame.draw.arc(s,(200,190,170),(8,4,20,20),0.5,2.6,2)
            pygame.draw.polygon(s,col,[(18,18),(24,25),(18,32),(12,25)])
            pygame.draw.polygon(s,(min(255,col[0]+50),min(255,col[1]+50),min(255,col[2]+50)),
                                [(18,21),(21,25),(18,29),(15,25)])
        return s

# ─── Dataclasses ────────────────────────────────────────────────
@dataclass
class Projectile:
    x:float;y:float;dx:float;dy:float
    speed:float;dmg:int;kind:str;owner:str
    alive:bool=True;frame:int=0;pierce:bool=False

@dataclass
class Trap:
    tx:int;ty:int;dmg:int
    active:bool=True;triggered:bool=False;timer:int=0

# ─── Partiküller ─────────────────────────────────────────────────
@dataclass
class Particle:
    x:float;y:float;vx:float;vy:float
    life:int;max_life:int;color:Tuple;size:int=3

class PS:
    def __init__(self): self.p:List[Particle]=[]
    def emit(self,x,y,n=8,col=(255,200,50),spd=3.0,life=30):
        for _ in range(n):
            a=random.uniform(0,math.pi*2);s=random.uniform(0.5,spd)
            self.p.append(Particle(float(x),float(y),math.cos(a)*s,math.sin(a)*s,life,life,col,random.randint(2,4)))
    def emit_hit(self,x,y): self.emit(x,y,12,HP_R,4.0,25);self.emit(x,y,6,(255,200,100),2.0,15)
    def emit_xp(self,x,y):  self.emit(x,y,10,XP_T,3.0,40)
    def emit_magic(self,x,y,col=None): self.emit(x,y,15,col or UI_AC,5.0,35)
    def emit_gold(self,x,y): self.emit(x,y,12,UI_GD,4.0,45)
    def update(self):
        alive=[]
        for pp in self.p:
            pp.x+=pp.vx;pp.y+=pp.vy;pp.vy+=0.07;pp.life-=1
            if pp.life>0: alive.append(pp)
        self.p=alive
    def draw(self,surf,cx,cy):
        for pp in self.p:
            a=int(255*pp.life/pp.max_life)
            ss=pygame.Surface((pp.size*2,pp.size*2),pygame.SRCALPHA)
            pygame.draw.circle(ss,(*pp.color[:3],a),(pp.size,pp.size),pp.size)
            surf.blit(ss,(int(pp.x-cx)-pp.size,int(pp.y-cy)-pp.size))

# ─── PlayerStats ─────────────────────────────────────────────────
class PlayerStats:
    def __init__(self,char_class="warrior"):
        self.char_class=char_class
        self.str=2;self.int_=2;self.agi=2;self.vit=2;self.wis=2
        bonus=CLASS_INFO[char_class]["bonus"]
        for k,v in bonus.items():
            if k=="int": self.int_+=v
            else: setattr(self,k,getattr(self,k)+v)
        self.hp=self.max_hp;self.mp=self.max_mp
        self.xp=0;self.level=1;self.gold=20;self.xp_next=50
        self.skill_points=0
        self.ab_cds=[0,0,0,0]
        self.buffs:Dict={}
        # Ekipman yuvaları
        self.equipment:Dict[str,Optional[str]]={"weapon":None,"armor":None,"ring":None}
        # Sınıfa özel auto-attack cooldown
        self.atk_cd=0

    @property
    def max_hp(self): return 40+self.vit*12
    @property
    def max_mp(self): return 12+self.wis*8
    @property
    def attack(self):
        base=4+self.str*2
        if "war_cry" in self.buffs: base=int(base*1.6)
        base+=self._equip_bonus("str")*2
        return base
    @property
    def magic_atk(self): return 4+(self.int_+self._equip_bonus("int"))*2
    @property
    def defense(self): return 1+(self.vit+self._equip_bonus("vit"))+(self.str+self._equip_bonus("str"))//3
    @property
    def crit(self): return min(0.5,0.05+(self.agi+self._equip_bonus("agi"))*0.02)
    @property
    def move_delay(self): return max(4,11-(self.agi+self._equip_bonus("agi"))//2)
    @property
    def atk_max_cd(self):
        base={"warrior":20,"mage":28,"archer":22,"healer":24}.get(self.char_class,22)
        return max(8,base-self._equip_bonus("agi"))

    def _equip_bonus(self,stat):
        total=0
        for slot,item_k in self.equipment.items():
            if item_k and item_k in EQUIP_ITEMS:
                _,_,bonus,_,_=EQUIP_ITEMS[item_k]
                total+=bonus.get(stat,0)
        return total

    def equip(self,item_k)->str:
        if item_k not in EQUIP_ITEMS: return "Ekipman degil"
        _,_,_,slot,cls_set=EQUIP_ITEMS[item_k]
        if cls_set and self.char_class not in cls_set:
            return f"Bu ekipmani {self.char_class} kullanamaz"
        old=self.equipment[slot]
        self.equipment[slot]=item_k
        return old or ""

    def unequip(self,slot)->Optional[str]:
        old=self.equipment.get(slot)
        self.equipment[slot]=None
        return old

    def heal(self,amt): self.hp=min(self.hp+amt,self.max_hp)
    def restore_mp(self,amt): self.mp=min(self.mp+amt,self.max_mp)
    def gain_xp(self,amt)->bool:
        self.xp+=amt
        if self.xp>=self.xp_next:
            self.xp-=self.xp_next;self.level+=1;self.xp_next=int(self.xp_next*1.55)
            self.skill_points+=3;self.heal(20);self.restore_mp(10);return True
        return False
    def tick_cds(self):
        self.ab_cds=[max(0,c-1) for c in self.ab_cds]
        if self.atk_cd>0: self.atk_cd-=1
    def tick_buffs(self):
        dead=[]
        for k,v in self.buffs.items():
            if isinstance(v,int): self.buffs[k]-=1
            if isinstance(self.buffs[k],int) and self.buffs[k]<=0: dead.append(k)
        for k in dead: del self.buffs[k]
    def can_use(self,slot)->bool:
        ab=ABILITIES.get(self.char_class,[])
        if slot>=len(ab): return False
        a=ab[slot]
        return self.level>=a["level"] and self.ab_cds[slot]==0 and self.mp>=a["mp"]
    def apply_item(self,stat,val):
        sk={"stat_str":"str","stat_int":"int","stat_agi":"agi","stat_vit":"vit","stat_wis":"wis"}.get(stat,stat)
        if sk=="str": self.str=min(30,self.str+val)
        elif sk=="int": self.int_=min(30,self.int_+val)
        elif sk=="agi": self.agi=min(30,self.agi+val)
        elif sk=="vit": self.vit=min(30,self.vit+val)
        elif sk=="wis": self.wis=min(30,self.wis+val)

# ─── Entities ───────────────────────────────────────────────────
def _tag_font():
    """İsim etiketleri için paylaşılan font — her karede yeniden yüklenmesin."""
    if _tag_font.cache is None:
        _tag_font.cache=pygame.font.SysFont("monospace",9,bold=True)
    return _tag_font.cache
_tag_font.cache=None

# Etiket yüzeyleri de metin başına bir kez üretilir (NPC adı, boss HP yazısı).
_TAG_SURF:Dict=dict()
def _tag_surf(text,col=WH):
    key=(text,col)
    s=_TAG_SURF.get(key)
    if s is None:
        s=_tag_font().render(text,True,col);_TAG_SURF[key]=s
    return s

class Entity:
    def __init__(self,tx,ty):
        self.tx=tx;self.ty=ty;self.px=float(tx*TILE);self.py=float(ty*TILE)
        self.direction="down";self.frame=0
        # Yumuşak hareket: px/py hedefe doğru ilerler, tx/ty anında güncellenir.
        self.from_px=self.px;self.from_py=self.py
        self.move_t=1.0;self.move_dur=1.0

    @property
    def moving(self)->bool: return self.move_t<1.0

    def start_step(self,ntx,nty,dur_frames:float):
        """tx/ty'yi hemen hedefe alır, piksel konumu araya yayılır."""
        self.from_px=self.px;self.from_py=self.py
        self.tx=ntx;self.ty=nty
        self.move_t=0.0;self.move_dur=max(1.0,float(dur_frames))

    def advance_step(self):
        if self.move_t>=1.0:
            self.px=float(self.tx*TILE);self.py=float(self.ty*TILE);return
        self.move_t=min(1.0,self.move_t+1.0/self.move_dur)
        tx_px=self.tx*TILE;ty_px=self.ty*TILE
        self.px=self.from_px+(tx_px-self.from_px)*self.move_t
        self.py=self.from_py+(ty_px-self.from_py)*self.move_t

    def snap(self,tx,ty):
        """Işınlanma (harita geçişi, yetenek): ara animasyon olmadan yerleştir."""
        self.tx=tx;self.ty=ty
        self.px=float(tx*TILE);self.py=float(ty*TILE)
        self.from_px=self.px;self.from_py=self.py;self.move_t=1.0

class Player(Entity):
    def __init__(self,tx,ty,stats):
        super().__init__(tx,ty);self.stats=stats
        self.inventory:List[str]=["hp_pot"]
        self.quest_items:List[str]=[]
        self.invincible=0;self.attacking=False;self.atk_frame=0;self.atk_max=15
    def draw(self,surf,cx,cy):
        if self.invincible>0 and (self.invincible//4)%2==1: return
        surf.blit(PA.player_surf(self.direction,self.frame,self.stats.char_class),
                  (int(self.px-cx),int(self.py-cy)))

class NPC(Entity):
    def __init__(self,tx,ty,name,color,dialog_fn,style="default"):
        super().__init__(tx,ty);self.name=name;self.color=color;self.dialog_fn=dialog_fn;self.style=style
        # Boşta gezinme: kendi köşesinden fazla uzaklaşmaz
        self.home_tx=tx;self.home_ty=ty
        self.idle_cd=random.randint(90,420)
    def get_dialog(self,flags): return self.dialog_fn(flags)
    def draw(self,surf,cx,cy):
        sx=int(self.px-cx); sy=int(self.py-cy)
        if not(-TILE<=sx<SW+TILE and -TILE<=sy<SH+TILE): return
        surf.blit(PA.npc_surf(self.color,self.frame,self.style),(sx,sy))
        tag=_tag_surf(T_(self.name))
        tx2=sx+TILE//2-tag.get_width()//2;ty2=sy-14
        if 0<=tx2<SW and 0<=ty2<SH:
            bg=pygame.Surface((tag.get_width()+4,tag.get_height()+2),pygame.SRCALPHA)
            bg.fill((0,0,0,160));surf.blit(bg,(tx2-2,ty2-1));surf.blit(tag,(tx2,ty2))

class Enemy(Entity):
    def __init__(self,tx,ty,kind,hp,atk,xp,agro=5,loot=None,is_boss=False):
        super().__init__(tx,ty)
        self.kind=kind;self.max_hp=hp;self.hp=hp;self.atk=atk;self.xp_r=xp
        self.agro_range=agro*TILE;self.loot=loot or [];self.is_boss=is_boss
        self.alive=True;self.state="idle";self.move_cd=0;self.frozen=0
        self.wind_up=0;self.atk_cd=0   # saldırı telegrafı
    def draw(self,surf,cx,cy):
        if not self.alive: return
        bx=int(self.px-cx); by=int(self.py-cy)
        if not(-TILE*2<=bx<SW+TILE*2 and -TILE*2<=by<SH+TILE*2): return
        sp=PA.enemy_surf(self.kind,self.frame)
        if self.kind=="malachar": surf.blit(sp,(bx-TILE//2,by-TILE//2))
        else: surf.blit(sp,(bx,by))
        if self.frozen>0:
            fs=pygame.Surface((TILE,TILE),pygame.SRCALPHA);fs.fill((100,180,255,80));surf.blit(fs,(bx,by))
        if self.wind_up>0:
            # Saldırı hazırlığı: kırmızı halka daralır + ünlem. Oyuncuya kaçma penceresi.
            t=1.0-self.wind_up/26.0
            r=int(TILE*0.9-TILE*0.35*t)
            ws=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA)
            pygame.draw.circle(ws,(255,70,60,150),(TILE,TILE),max(3,r),3)
            surf.blit(ws,(bx-TILE//2,by-TILE//2))
            ex=_tag_surf("!",(255,90,80))
            surf.blit(ex,(bx+TILE//2-ex.get_width()//2,by-24))
        bw=56 if self.is_boss else 28;bh=5 if self.is_boss else 4
        bbx=bx+(TILE-bw)//2;bby=by+(-14 if self.is_boss else -8)
        pygame.draw.rect(surf,HP_R,(bbx,bby,bw,bh))
        pygame.draw.rect(surf,HP_G,(bbx,bby,int(bw*max(0,self.hp)/self.max_hp),bh))
        pygame.draw.rect(surf,BK,(bbx,bby,bw,bh),1)
        if self.is_boss:
            tt=_tag_surf(f"{self.kind.upper()} {self.hp}/{self.max_hp}",UI_TX)
            surf.blit(tt,(bbx+bw//2-tt.get_width()//2,bby-12))

# ─── Ortam ışığı ────────────────────────────────────────────────
# Karanlık haritalar düz bir renk katmanıyla kapatılıyordu; zemin okunmuyordu.
# Artık katman biraz açıldı ve oyuncunun çevresinde bir ışık halesi açılıyor.
LIGHT_R = 190          # ışık halesinin yarıçapı (px)
_AMBIENT_ALPHA = 105   # halenin dışındaki karanlık
_hole_cache = {}

def _light_hole(radius,max_alpha):
    """Merkezi şeffaf, kenarı opak maske. BLEND_RGBA_MIN ile katmanda delik açar.

    Tepe alfa, ortam katmanının alfasıyla aynı olmalı: 0-255 arasında bir
    degrade üretilirse maske kenara varmadan katmanın alfasını geçer ve
    BLEND_RGBA_MIN yüzünden geçişin dış kısmı düz karanlığa doyar.
    """
    key=(radius,max_alpha)
    s=_hole_cache.get(key)
    if s is None:
        d=radius*2
        s=pygame.Surface((d,d),pygame.SRCALPHA);s.fill((255,255,255,max_alpha))
        # Büyükten küçüğe çiziyoruz; her küçük daire içini ezdiği için
        # alfa da küçülmeli: kenar opak (karanlık), merkez şeffaf (aydınlık).
        steps=40
        for i in range(steps):
            t=i/(steps-1)
            r=int(radius*(1.0-t*0.97))
            a=int(max_alpha*((1.0-t)**1.4))
            pygame.draw.circle(s,(255,255,255,a),(radius,radius),max(1,r))
        _hole_cache[key]=s
    return s

def _draw_ambient(surf,color,light_at=None,alpha=_AMBIENT_ALPHA):
    ov=pygame.Surface((SW,SH),pygame.SRCALPHA)
    ov.fill((*color,alpha))
    if light_at:
        lx,ly=light_at
        hole=_light_hole(LIGHT_R,alpha)
        ov.blit(hole,(int(lx-LIGHT_R),int(ly-LIGHT_R)),special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(ov,(0,0))

# ─── GameMap ────────────────────────────────────────────────────
class GameMap:
    def __init__(self,w,h,name,ambient=(0,0,0)):
        self.w=w;self.h=h;self.name=name;self.ambient=ambient
        self.base_chests=set()   # kayit/yukleme: hangi sandiklar aslinda vardi
        self.light_at=None       # isik halesinin ekran konumu (oyuncu)
        self.props=[]            # (tx,ty,kind) — yurumeyi engellemeyen dekor
        self.tiles=[[T.GRASS]*w for _ in range(h)]
        self._sc:Dict={};self.anim=0
        self.npcs:List[NPC]=[];self.enemies:List[Enemy]=[]
        self.chests:Dict[Tuple,List]={};self.transitions:Dict[Tuple,Tuple]={}
        self.traps:List[Trap]=[]
        # Geçiş göstergesi: (tx,ty) -> yön (dx,dy,dst_name)
        self.trans_hints:Dict[Tuple,Tuple]={}
    def set(self,tx,ty,tile):
        if 0<=tx<self.w and 0<=ty<self.h: self.tiles[ty][tx]=tile
    def get(self,tx,ty):
        if 0<=tx<self.w and 0<=ty<self.h: return self.tiles[ty][tx]
        return T.STONE
    def walkable(self,tx,ty): return self.get(tx,ty) in WALKABLE
    def _ts(self,tile):
        if tile in(T.WATER,T.RIVER): return PA.tile(tile,self.anim)
        if tile not in self._sc: self._sc[tile]=PA.tile(tile)
        return self._sc[tile]
    def draw(self,surf,cx,cy,tick=0):
        self.anim+=1
        sx=cx//TILE;sy=cy//TILE;ex=sx+SW//TILE+2;ey=sy+SH//TILE+2
        for ty in range(max(0,sy),min(self.h,ey)):
            for tx in range(max(0,sx),min(self.w,ex)):
                surf.blit(self._ts(self.tiles[ty][tx]),(tx*TILE-cx,ty*TILE-cy))
        if self.ambient!=(0,0,0):
            _draw_ambient(surf,self.ambient,self.light_at)
        # Geçiş göstergeleri (küçük parlayan oklar — bloklama yok)
        for (tx,ty),(ddx,ddy,dname) in self.trans_hints.items():
            sx2=tx*TILE-cx;sy2=ty*TILE-cy
            if not(-TILE<=sx2<SW+TILE and -TILE<=sy2<SH+TILE): continue
            gv=int(abs(math.sin(tick*0.004))*80)+80
            hs=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            hs.fill((gv,gv//2,min(255,gv*2),40))
            ang_map={(1,0):0,(-1,0):180,(0,-1):90,(0,1):270}
            ang=ang_map.get((ddx,ddy),0)
            # Ok çiz
            cx2=TILE//2;cy2=TILE//2
            pts=[(cx2+10,cy2),(cx2-6,cy2-7),(cx2-6,cy2+7)]
            import math as _m
            rad=_m.radians(ang)
            rot_pts=[(int(cx2+(px-cx2)*_m.cos(rad)-(py-cy2)*_m.sin(rad)),
                      int(cy2+(px-cx2)*_m.sin(rad)+(py-cy2)*_m.cos(rad))) for px,py in pts]
            pygame.draw.polygon(hs,(min(255,gv+120),160,255,min(200,gv+120)),rot_pts)
            surf.blit(hs,(sx2,sy2))
        for (ptx,pty,kind) in self.props:
            sx3=ptx*TILE-cx;sy3=pty*TILE-cy
            if -TILE<=sx3<SW and -TILE<=sy3<SH: surf.blit(PA.prop_surf(kind),(sx3,sy3))
        for tt in self.traps:
            if tt.active: surf.blit(PA.trap_surf(tt.triggered),(tt.tx*TILE-cx,tt.ty*TILE-cy))
        for e in self.npcs: e.frame+=1;e.draw(surf,cx,cy)
        for e in self.enemies:
            if e.alive: e.frame+=1;e.draw(surf,cx,cy)

# ─── Map Yardımcıları ────────────────────────────────────────────
def _rect(m,x,y,w,h,tile):
    for ty in range(y,y+h):
        for tx in range(x,x+w): m.set(tx,ty,tile)

def _room(m,rx,ry,rw,rh,wall,floor,door="south"):
    for ty in range(ry,ry+rh):
        for tx in range(rx,rx+rw):
            if ty in(ry,ry+rh-1) or tx in(rx,rx+rw-1): m.set(tx,ty,wall)
            else: m.set(tx,ty,floor)
    if door=="south": m.set(rx+rw//2,ry+rh-1,T.DOOR)
    elif door=="north": m.set(rx+rw//2,ry,T.DOOR)
    elif door=="east": m.set(rx+rw-1,ry+rh//2,T.DOOR)
    elif door=="west": m.set(rx,ry+rh//2,T.DOOR)

def _path(m,x1,y1,x2,y2,tile,pw=2):
    steps=max(abs(x2-x1),abs(y2-y1))
    if steps==0: return
    for i in range(steps+1):
        tx=int(x1+(x2-x1)*i/steps);ty=int(y1+(y2-y1)*i/steps)
        for dw in range(-(pw//2),(pw+1)//2):
            if abs(x2-x1)>=abs(y2-y1): m.set(tx,ty+dw,tile)
            else: m.set(tx+dw,ty,tile)

def _snap(m,tx,ty):
    if m.walkable(tx,ty): return (tx,ty)
    visited={(tx,ty)};q=deque([(tx,ty)])
    while q:
        cx,cy=q.popleft()
        for dx,dy in[(-1,0),(1,0),(0,-1),(0,1),(1,1),(-1,-1),(1,-1),(-1,1)]:
            nx,ny=cx+dx,cy+dy
            if(nx,ny) in visited or not(0<=nx<m.w and 0<=ny<m.h): continue
            visited.add((nx,ny))
            if m.walkable(nx,ny): return (nx,ny)
            q.append((nx,ny))
    return (tx,ty)

# Zemin türüne göre hangi dekorlar serpiştirilir
_PROPS_BY_TILE = {
    T.GRASS: ("flower","bush","grasstuft","grasstuft","rock","stump"),
    T.DIRT:  ("rock","grasstuft","stump"),
    T.SAND:  ("rock","bone","bone"),
    T.SNOW:  ("rock","crystal"),
    T.FLOOR: ("rock","mushroom"),        # ev/zindan zemini — kemik coleye ait
}

def _scatter_props(m,density=0.07):
    """Haritaya dekor serpiştirir.

    Tohum harita adından üretiliyor: her açılışta aynı görünüm çıkar,
    yani kayıtta tutmaya gerek yok. Dekorlar yürümeyi engellemez ve
    geçiş/sandık/NPC karelerine konmaz.

    NOT: Python'da str.hash() süreçler arası rastgeledir (PYTHONHASHSEED),
    bu yüzden kararlı bir özet olan crc32 kullanılıyor — yoksa dekor her
    açılışta yeniden dizilirdi.
    """
    rng=random.Random(zlib.crc32(m.name.encode("utf-8")))
    busy={(n.tx,n.ty) for n in m.npcs}
    busy|={(e.tx,e.ty) for e in m.enemies}
    busy|=set(m.chests)|set(m.transitions)|set(m.trans_hints)
    for ty in range(m.h):
        for tx in range(m.w):
            if (tx,ty) in busy: continue
            kinds=_PROPS_BY_TILE.get(m.tiles[ty][tx])
            if not kinds or rng.random()>density: continue
            m.props.append((tx,ty,rng.choice(kinds)))

def _snap_all(m):
    occ=set()
    for e in m.npcs+m.enemies:
        tx,ty=_snap(m,e.tx,e.ty);att=0
        while(tx,ty) in occ and att<30:
            tx2,ty2=_snap(m,tx+(att%5)-2,ty+(att//5)-2)
            if(tx2,ty2) not in occ: tx,ty=tx2,ty2;break
            att+=1
        e.snap(tx,ty);occ.add((tx,ty))

def _add_trans(m,tiles,dst,dtx,dty,ground=T.GRASS,hint_dir=(1,0)):
    """Geçiş ekle — tile normal zemin olur, görsel ok gösterilir."""
    for tx,ty in tiles:
        m.set(tx,ty,ground)
        m.transitions[(tx,ty)]=(dst,dtx,dty)
        m.trans_hints[(tx,ty)]=(hint_dir[0],hint_dir[1],dst)

# ─── Haritalar ───────────────────────────────────────────────────

# ─── Yardımcı: Tek Şerit Geçiş ─────────────────────────────────
def _trans_strip(m, axis, fixed, start, end, dst, dtx, dty, ground=None, hint=None):
    """
    Haritanın bir kenarına TEK TILE sırası geçiş koyar.
    axis='x' → dikey şerit (fixed=tx, start/end=ty aralığı)
    axis='y' → yatay şerit (fixed=ty, start/end=tx aralığı)
    Geçiş tile'ları normal zemin olur, karakteri bloke etmez.
    Spawn noktası (dtx,dty) güvenli konuma snap edilir.
    """
    if ground is None:
        ground = T.GRASS
    if hint is None:
        hint = (1,0) if axis=='x' else (0,1)
    tiles = []
    if axis == 'x':
        for ty in range(start, end):
            m.set(fixed, ty, ground)
            m.transitions[(fixed,ty)] = (dst, dtx, dty)
            m.trans_hints[(fixed,ty)] = (hint[0], hint[1], dst)
    else:
        for tx in range(start, end):
            m.set(tx, fixed, ground)
            m.transitions[(tx,fixed)] = (dst, dtx, dty)
            m.trans_hints[(tx,fixed)] = (hint[0], hint[1], dst)


def build_ashveil():
    m = GameMap(62, 52, "map.ashveil_koyu")
    _rect(m, 0, 0, 62, 52, T.GRASS)
    # Göl
    for ty in range(3, 12):
        for tx in range(2, 15):
            if (tx-8)**2 + (ty-7)**2 < 22: m.set(tx, ty, T.WATER)
    for ty in range(2, 13):
        for tx in range(1, 17):
            if m.get(tx,ty)==T.GRASS and any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                m.set(tx, ty, T.SAND)
    # Ana yollar
    _path(m, 2, 24, 60, 24, T.STONE, 2)
    _path(m, 30, 2, 30, 50, T.STONE, 2)
    # Evler — yoldan uzak, bağlantılı
    _room(m, 16,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 34,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 16, 30, 10, 8, T.WALL, T.FLOOR, "north")
    _room(m, 34, 30, 10, 8, T.WALL, T.FLOOR, "north")
    _path(m, 20, 15, 20, 24, T.STONE, 2)
    _path(m, 38, 15, 38, 24, T.STONE, 2)
    _path(m, 20, 30, 20, 24, T.STONE, 2)
    _path(m, 38, 30, 38, 24, T.STONE, 2)
    # Sandıklar
    m.set(18, 10, T.CHEST); m.chests[(18,10)] = ["hp_pot","gold"]
    m.set(36, 10, T.CHEST); m.chests[(36,10)] = ["mp_pot","iron_sword"]
    m.set(18, 32, T.CHEST); m.chests[(18,32)] = ["leather_armor","gold"]
    # Zindan — taş yol üzerinde
    _path(m, 28, 44, 34, 44, T.DIRT, 2)
    _trans_strip(m, 'y', 46, 28, 34, "village_dungeon", 19, 3, T.DIRT, (0,1))

    # ── SAĞDA SABİT ORMAN KORİDORU (y=20..28 geçit) ──
    for ty in range(0, 52):
        for tx in range(44, 62):
            if 20 <= ty <= 28:
                m.set(tx, ty, T.GRASS)
            else:
                col = (tx-44) % 6; row = ty % 6
                if col < 3 and row < 3:
                    m.set(tx, ty, T.TREE)
    for tx in range(40, 62):
        m.set(tx, 23, T.STONE); m.set(tx, 24, T.STONE)
    for ty in range(20, 29):
        for tx in range(40, 62):
            if m.get(tx, ty) == T.TREE: m.set(tx, ty, T.GRASS)

    # Sınır
    for tx in range(0,62): m.set(tx,0,T.TREE); m.set(tx,1,T.TREE)
    for ty in range(0,52): m.set(0,ty,T.TREE); m.set(1,ty,T.TREE)

    # ── GEÇİŞLER (tek tile şeridi, karşı taraf güvenli spawn) ──
    # Sağ → Karanlık Orman  (y=20..28, x=60)
    _trans_strip(m,'x',60, 21,28, "dark_forest", 5,22, T.GRASS,(1,0))
    # Güney → Çayır  (x=22..38, y=50)
    _trans_strip(m,'y',50, 22,38, "south_meadow",22, 3, T.GRASS,(0,1))
    # Batı → Nehir  (y=20..28, x=2)
    _trans_strip(m,'x',2,  21,28, "west_river",  52,22, T.GRASS,(-1,0))

    # NPCler
    def aldric_d(f):
        if f.get("ch",1)>=6: return ["dlg.aldric.1","dlg.aldric.2"]
        if f.get("water_crystal"): return ["dlg.aldric.3","dlg.aldric.4","dlg.aldric.5"]
        if f.get("earth_crystal"): return ["dlg.aldric.6","dlg.aldric.7","dlg.aldric.8","dlg.aldric.9"]
        return ["dlg.aldric.10","dlg.aldric.11","dlg.aldric.12","dlg.aldric.13","dlg.aldric.14"]
    m.npcs.append(NPC(24,19,"npc.yasli_aldric",(160,100,60),aldric_d,"elder"))
    def smith_d(f): return ["dlg.smith.1","dlg.smith.2","dlg.smith.3"]
    m.npcs.append(NPC(18,13,"npc.demirci_boran",(140,90,50),smith_d,"smith"))
    def inn_d(f): return ["dlg.inn.1","dlg.inn.2","dlg.inn.3"]
    m.npcs.append(NPC(38,13,"npc.hanci_mira",(180,130,160),inn_d,"inn"))
    def guard_d(f):
        if not f.get("speak_aldric"): return ["dlg.guard.1","dlg.guard.2"]
        return ["dlg.guard.3","dlg.guard.4","dlg.guard.5"]
    m.npcs.append(NPC(56,22,"npc.koy_muhafizi",(100,120,180),guard_d,"guard"))
    def south_d(f): return ["dlg.south.1","dlg.south.2"]
    m.npcs.append(NPC(24,48,"npc.yolcu",(160,180,140),south_d,"traveler"))
    def west_d(f): return ["dlg.west.1","dlg.west.2","dlg.west.3"]
    m.npcs.append(NPC(4,24,"npc.koy_yerlisi",(140,160,180),west_d))
    m.enemies += [
        Enemy(48,12,"slime",20,4,12,agro=4,loot=["gold"]),
        Enemy(52,8, "slime",20,4,12,agro=4),
        Enemy(56,14,"goblin",35,7,22,agro=5,loot=["hp_pot"]),
    ]
    _snap_all(m); return m


def build_dark_forest():
    """Karanlık Orman — sabit tasarım, güney/batı çıkışları var."""
    m = GameMap(58, 48, "map.karanlik_orman", ambient=(0,20,0))
    _rect(m, 0, 0, 58, 48, T.GRASS)
    # Kenar 2 tile ağaç
    for ty in range(48):
        m.set(0,ty,T.DARK_TREE); m.set(1,ty,T.DARK_TREE)
        m.set(56,ty,T.DARK_TREE); m.set(57,ty,T.DARK_TREE)
    for tx in range(58):
        m.set(tx,0,T.DARK_TREE); m.set(tx,1,T.DARK_TREE)
        m.set(tx,46,T.DARK_TREE); m.set(tx,47,T.DARK_TREE)
    # Sabit ağaç grupları — köşelerde, yollardan uzak
    for tx,ty in [
        (4,4),(5,4),(6,4),(4,5),(5,5),(8,4),(9,4),(10,4),(8,5),(9,5),
        (4,8),(5,8),(4,9),(5,9),(8,8),(9,8),(10,8),(8,9),(9,9),
        (44,4),(45,4),(46,4),(44,5),(45,5),(48,4),(49,4),(50,4),(48,5),(49,5),
        (44,8),(45,8),(46,8),(44,9),(45,9),(48,8),(49,8),(50,8),(48,9),(49,9),
        (4,34),(5,34),(6,34),(4,35),(5,35),(8,34),(9,34),(10,34),(8,35),(9,35),
        (4,38),(5,38),(4,39),(5,39),(8,38),(9,38),(10,38),(8,39),(9,39),
        (44,34),(45,34),(46,34),(44,35),(45,35),(48,34),(49,34),(50,34),
        (44,38),(45,38),(46,38),(44,39),(45,39),(48,38),(49,38),(50,38),
    ]:
        m.set(tx,ty,T.DARK_TREE)
    # Ana yollar — tamamen temiz
    for ty in range(18,28):
        for tx in range(58):
            if m.get(tx,ty)==T.DARK_TREE: m.set(tx,ty,T.GRASS)
    _path(m,0,22,58,22,T.DIRT,2)
    for ty in range(48):
        for tx in range(25,33):
            if m.get(tx,ty)==T.DARK_TREE: m.set(tx,ty,T.GRASS)
    _path(m,28,0,28,48,T.DIRT,2)

    # ── GEÇİŞLER ──
    # Sol → Ashveil  (y=21..27, x=2)
    _trans_strip(m,'x',2, 21,27, "ashveil",   59,24, T.GRASS,(-1,0))
    # Kuzey → Antik Harabeler  (x=25..31, y=2)
    _trans_strip(m,'y',2, 25,31, "ruins",      16,46, T.GRASS,(0,-1))
    # Güney → Kayalık Geçit  (x=25..31, y=46)
    _trans_strip(m,'y',46,25,31, "rocky_pass",  28, 3, T.GRASS,(0,1))
    # Batı alt → Sisli Bataklık  (y=32..40, x=2)
    _trans_strip(m,'x',2, 32,40, "misty_swamp", 55,20, T.GRASS,(-1,0))

    # Sandıklar
    m.set(16,14,T.CHEST); m.chests[(16,14)] = ["hp_pot","fine_bow"]
    m.set(40,14,T.CHEST); m.chests[(40,14)] = ["mp_pot","power_ring"]
    m.set(16,30,T.CHEST); m.chests[(16,30)] = ["leather_armor","gold"]

    def roland_d(f):
        if f.get("ch",1)>=3: return ["dlg.roland.1","dlg.roland.2","dlg.roland.3"]
        return ["dlg.roland.4","dlg.roland.5","dlg.roland.6","dlg.roland.7","dlg.roland.8"]
    m.npcs.append(NPC(22,22,"npc.sir_roland",(130,160,130),roland_d,"knight"))

    m.enemies += [
        Enemy(16,12,"wolf",35,8,20,agro=5,loot=["gold"]),
        Enemy(38,12,"wolf",35,8,20,agro=5),
        Enemy(42,18,"goblin",40,9,25,agro=5,loot=["hp_pot"]),
        Enemy(16,32,"skeleton",50,11,32,agro=6,loot=["mp_pot"]),
        Enemy(40,32,"goblin",45,10,28,agro=6,loot=["gold"]),
        Enemy(30,28,"wolf",42,9,22,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_rocky_pass():
    """Kayalık Geçit — Karanlık Orman'ın güneyinde, çöle bağlı."""
    m = GameMap(48, 38, "map.kayalik_gecit", ambient=(15,10,5))
    _rect(m, 0, 0, 48, 38, T.STONE)
    # Yürünebilir zemin (dağ geçidi)
    # Tüm iç alanı zemin yap, sonra kayalar ekle
    _rect(m, 2, 2, 44, 34, T.DIRT)
    # Sabit kayalar (bloke etmez, sadece dekor)
    for tx,ty in [(10,5),(11,5),(18,5),(19,5),(28,5),(29,5),(36,5),(37,5),
                  (10,14),(11,14),(18,14),(19,14),(30,14),(31,14),
                  (10,22),(11,22),(22,22),(23,22),(34,22),(35,22)]:
        m.set(tx,ty,T.RUINS_WALL)
    # Sabit kayalar (dekoratif, yolları kapatmaz)
    for tx,ty in [(12,4),(13,4),(20,4),(21,4),(28,4),(29,4),(36,4),(37,4),
                  (12,18),(13,18),(20,18),(21,18),(30,18),(31,18),
                  (10,28),(11,28),(22,28),(23,28),(34,28),(35,28)]:
        m.set(tx,ty,T.RUINS_WALL)
    # Duvar düzelt
    for ty in range(38):
        for tx in range(48):
            if m.get(tx,ty)==T.STONE:
                if any(m.get(tx+dx,ty+dy)==T.DIRT for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.RUINS_WALL)

    # Dış çerçeve
    for tx in range(48): m.set(tx,0,T.RUINS_WALL); m.set(tx,37,T.RUINS_WALL)
    for ty in range(38): m.set(0,ty,T.RUINS_WALL); m.set(47,ty,T.RUINS_WALL)
    # GEÇİŞLER
    _trans_strip(m,'y',1, 20,28, "dark_forest",  27,45, T.DIRT,(0,-1))
    _trans_strip(m,'y',36,20,28, "desert",        20, 4, T.DIRT,(0,1))
    _trans_strip(m,'x',46,15,23, "ruins",          2,21, T.DIRT,(1,0))

    m.set(8,  4, T.CHEST); m.chests[(8, 4)]  = ["hp_pot","hp_pot","gold"]
    m.set(36, 4, T.CHEST); m.chests[(36,4)]  = ["mp_pot","power_ring"]
    m.set(24,28, T.CHEST); m.chests[(24,28)] = ["hp_pot","iron_sword","gold"]

    def scout_d(f): return ["dlg.scout.1","dlg.scout.2","dlg.scout.3","dlg.scout.4"]
    m.npcs.append(NPC(24,16,"npc.gecit_gozcusu",(160,140,100),scout_d,"guard"))

    m.enemies += [
        Enemy(14, 6,"goblin",42,9,26,agro=5,loot=["gold"]),
        Enemy(30, 6,"goblin",42,9,26,agro=5),
        Enemy(10,18,"wolf",  38,9,22,agro=5,loot=["hp_pot"]),
        Enemy(36,18,"wolf",  38,9,22,agro=5),
        Enemy(14,26,"skeleton",52,11,30,agro=5,loot=["mp_pot"]),
        Enemy(32,26,"skeleton",52,11,30,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_misty_swamp():
    """Sisli Bataklık — Karanlık Orman'ın batısında."""
    m = GameMap(58, 42, "map.sisli_bataklik", ambient=(10,20,10))
    _rect(m, 0, 0, 58, 42, T.GRASS)
    # Bataklık su alanları (sabit)
    swamp_pools = [
        (4,4,8,6),(16,2,10,7),(30,4,8,5),(44,2,10,8),
        (2,18,6,8),(14,16,8,8),(28,14,10,10),(42,16,10,8),
        (4,28,8,8),(20,28,8,8),(34,26,10,10),(46,28,8,8),
    ]
    for rx,ry,rw,rh in swamp_pools:
        for ty in range(ry,ry+rh):
            for tx in range(rx,rx+rw):
                if 0<=tx<58 and 0<=ty<42: m.set(tx,ty,T.WATER)
    # Kum adacıkları (yürünebilir)
    for tx,ty in [(8,6),(9,6),(8,7),(12,8),(13,8),(12,9),
                  (22,9),(23,9),(26,6),(27,6),(36,7),(37,7),
                  (46,10),(47,10),(48,9),(10,22),(11,22),(10,23),
                  (20,20),(21,20),(22,21),(30,18),(31,18),(38,20),
                  (48,20),(49,20),(50,21),(8,32),(9,32),(14,30),
                  (26,32),(27,32),(40,28),(41,28),(50,32)]:
        m.set(tx,ty,T.SAND)
    # Bataklık yolu (ana geçit)
    _path(m, 2,20, 56,20, T.DIRT, 2)
    _path(m,28, 2, 28,40, T.DIRT, 2)
    # Kıyı şeridi
    for ty in range(42):
        for tx in range(58):
            if m.get(tx,ty)==T.GRASS:
                if any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.SAND)

    # GEÇİŞLER
    # Doğu → Karanlık Orman  (y=19..27, x=56)
    _trans_strip(m,'x',56,19,27, "dark_forest",  3,34, T.GRASS,(1,0))
    # Kuzey → Ashveil  (x=25..31, y=2) – opsiyonel kısa yol
    _trans_strip(m,'y',2, 25,31, "ashveil",      3,24, T.GRASS,(0,-1))

    m.set(26,20, T.CHEST); m.chests[(26,20)] = ["hp_pot","mp_pot","gold"]
    m.set(48,20, T.CHEST); m.chests[(48,20)] = ["hp_pot","power_ring"]
    m.set(10,20, T.CHEST); m.chests[(10,20)] = ["hp_pot","gold","gold"]
    m.set(46,20, T.CHEST); m.chests[(46,20)] = ["mp_pot","fine_bow"]

    def witch_d(f): return ["dlg.witch.1","dlg.witch.2","dlg.witch.3","dlg.witch.4"]
    m.npcs.append(NPC(30,19,"npc.bataklik_cadisi",(100,160,100),witch_d,"oracle"))

    m.enemies += [
        Enemy(10,20,"slime",   30, 6,18,agro=4,loot=["gold"]),
        Enemy(38,22,"slime",   30, 6,18,agro=4),
        Enemy(12,18,"goblin",  42, 9,26,agro=5,loot=["hp_pot"]),
        Enemy(44,18,"goblin",  42, 9,26,agro=5,loot=["gold"]),
        Enemy(10,30,"skeleton",52,11,30,agro=5,loot=["mp_pot"]),
        Enemy(44,30,"skeleton",52,11,30,agro=5,loot=["gold"]),
        Enemy(26,10,"boar",    45,10,28,agro=5,loot=["gold"]),
        Enemy(32,32,"boar",    45,10,28,agro=5),
    ]
    _snap_all(m); return m


def build_ruins():
    m = GameMap(58, 52, "map.antik_harabeler", ambient=(20,10,0))
    _rect(m, 0, 0, 58, 52, T.STONE)
    # Tüm iç alanı tek büyük zemin yap (duvarlar sonra)
    _rect(m, 2, 2, 54, 48, T.FLOOR)
    # Bölücü duvarlar (yatay — odaları ayırır)
    for tx in range(2,56):  m.set(tx,13,T.RUINS_WALL); m.set(tx,27,T.RUINS_WALL)
    # Bölücü duvarlar (dikey)
    for ty in range(2,50):  m.set(15,ty,T.RUINS_WALL); m.set(30,ty,T.RUINS_WALL)
    # Kapılar (her bölücü duvarda)
    for tx in [8,22,42]:    m.set(tx,13,T.FLOOR); m.set(tx+1,13,T.FLOOR)
    for tx in [8,22,42]:    m.set(tx,27,T.FLOOR); m.set(tx+1,27,T.FLOOR)
    for ty in [7,20,36]:    m.set(15,ty,T.FLOOR); m.set(15,ty+1,T.FLOOR)
    for ty in [7,20,36]:    m.set(30,ty,T.FLOOR); m.set(30,ty+1,T.FLOOR)
    # Boss bölmesi (sağ alt)
    for tx2 in range(31,55): m.set(tx2,36,T.RUINS_WALL)
    for ty2 in range(36,50): m.set(31,ty2,T.RUINS_WALL); m.set(54,ty2,T.RUINS_WALL)
    m.set(42,36,T.DOOR); m.set(43,36,T.DOOR)
    _rect(m,32,37,22,12,T.FLOOR)
    # Dış çerçeve duvarı
    for tx in range(58): m.set(tx,0,T.RUINS_WALL); m.set(tx,51,T.RUINS_WALL)
    for ty in range(52): m.set(0,ty,T.RUINS_WALL); m.set(57,ty,T.RUINS_WALL)

    # GEÇİŞLER — dış duvarda tek şerit, karşıdaki spawn oda içinde
    # Güney → Karanlık Orman
    _trans_strip(m,'y',50, 5,14, "dark_forest",  27, 3, T.FLOOR,(0,1))
    # Doğu → Çöl
    _trans_strip(m,'x',56,19,26, "desert",        3,27, T.FLOOR,(1,0))
    # Batı → Kayalık Geçit
    _trans_strip(m,'x',1, 19,26, "rocky_pass",   44,17, T.FLOOR,(-1,0))

    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["hp_pot","mp_pot"]
    m.set(20, 5,T.CHEST); m.chests[(20,5)] = ["arcane_staff","gold"]
    m.set(42, 5,T.CHEST); m.chests[(42,5)] = ["mage_robe","gold"]
    m.set(6, 20,T.CHEST); m.chests[(6,20)] = ["hp_pot","power_ring"]
    m.set(44,44,T.CHEST); m.chests[(44,44)]= ["earth_c","hp_pot","hp_pot"]

    def ghost_d(f):
        if f.get("earth_crystal"): return ["dlg.ghost.1","dlg.ghost.2"]
        return ["dlg.ghost.3","dlg.ghost.4"]
    m.npcs.append(NPC(8,19,"npc.antik_ruh",(180,200,220),ghost_d,"spirit"))
    m.enemies += [
        Enemy(6, 6,"skeleton",55,11,30,agro=5,loot=["gold"]),
        Enemy(22, 6,"skeleton",55,11,30,agro=5),
        Enemy(8, 19,"golem",  80,15,45,agro=4,loot=["gold","gold"]),
        Enemy(24,19,"skeleton",60,12,35,agro=5,loot=["hp_pot"]),
        Enemy(8, 33,"golem",  85,16,48,agro=4),
        Enemy(24,33,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(46,44,"golem", 130,20,80,agro=6,loot=["earth_c"],is_boss=True),
    ]
    _snap_all(m); return m


def build_desert():
    m = GameMap(60, 44, "map.col_yolu", ambient=(30,15,0))
    _rect(m, 0, 0, 60, 44, T.SAND)
    for rx,ry,rs in [(6,6,3),(16,6,3),(52,6,3),(56,9,2),(6,36,3),(14,38,2),(52,36,3),(56,38,2)]:
        for ty in range(ry-rs,ry+rs+1):
            for tx in range(rx-rs,rx+rs+1):
                if (tx-rx)**2+(ty-ry)**2<=rs*rs and 2<=tx<58 and 2<=ty<42:
                    m.set(tx,ty,T.STONE)
    for tx,ty in [(10,12),(20,8),(40,8),(50,14),(10,30),(20,36),(40,36),(50,28),(14,20),(46,20)]:
        if m.get(tx,ty)==T.SAND: m.set(tx,ty,T.CACTUS)
    for ty in range(14,22):
        for tx in range(26,36):
            if (tx-31)**2+(ty-18)**2<16: m.set(tx,ty,T.WATER)
    for ty in range(13,23):
        for tx in range(25,37):
            if m.get(tx,ty)==T.SAND and any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                m.set(tx,ty,T.GRASS)
    _room(m,27,5,8,6,T.WALL,T.FLOOR,"south")
    _path(m, 2,28,58,28,T.DIRT,2)
    # GEÇİŞLER
    _trans_strip(m,'x',2, 26,31, "ruins",    54,21, T.SAND,(-1,0))
    _trans_strip(m,'x',58,26,31, "ice_cave",  3,28, T.SAND,(1,0))
    _trans_strip(m,'y',2, 24,32, "rocky_pass",22,35, T.SAND,(0,-1))
    m.set(5, 28,T.CHEST); m.chests[(5,28)]  = ["hp_pot","hp_pot","gold"]
    m.set(54,28,T.CHEST); m.chests[(54,28)] = ["shadow_bow","gold"]
    m.set(30, 7,T.CHEST); m.chests[(30,7)]  = ["mage_focus","hp_pot"]
    def oracle_d(f):
        if f.get("water_crystal"): return ["dlg.oracle.1","dlg.oracle.2"]
        if f.get("earth_crystal"): return ["dlg.oracle.3","dlg.oracle.4"]
        return ["dlg.oracle.5","dlg.oracle.6"]
    m.npcs.append(NPC(30,8,"npc.oracle_nyx",(120,80,180),oracle_d,"oracle"))
    m.enemies += [
        Enemy(10,10,"scorpion",45,10,30,agro=5,loot=["gold"]),
        Enemy(48,10,"scorpion",45,10,30,agro=5),
        Enemy(10,34,"goblin",  50,11,32,agro=5,loot=["hp_pot"]),
        Enemy(48,34,"goblin",  50,11,32,agro=5,loot=["gold"]),
        Enemy(22,10,"scorpion",50,12,35,agro=6),
        Enemy(38,34,"goblin",  55,12,35,agro=5,loot=["mp_pot"]),
    ]
    _snap_all(m); return m


def build_ice_cave():
    m = GameMap(52, 48, "map.buz_magara", ambient=(0,15,30))
    _rect(m,0,0,52,48,T.STONE)
    ice_rooms=[
        (2,2,12,11),(16,2,12,11),(30,2,20,11),
        (2,15,12,13),(16,15,12,13),(30,15,20,13),
        (2,30,12,16),(16,30,12,16),(30,30,20,16),
    ]
    for rx,ry,rw,rh in ice_rooms: _rect(m,rx,ry,rw,rh,T.SNOW)
    _rect(m,3,3,8,6,T.ICE); _rect(m,17,3,8,6,T.ICE); _rect(m,31,3,8,6,T.ICE)
    _rect(m,14,5,2,5,T.SNOW); _rect(m,28,5,2,5,T.SNOW)
    _rect(m,14,18,2,7,T.SNOW); _rect(m,28,18,2,7,T.SNOW)
    _rect(m,14,33,2,9,T.SNOW); _rect(m,28,33,2,9,T.SNOW)
    _rect(m,5,13,5,2,T.SNOW); _rect(m,5,28,5,2,T.SNOW)
    _rect(m,19,13,5,2,T.SNOW); _rect(m,19,28,5,2,T.SNOW)
    _rect(m,36,13,5,2,T.SNOW); _rect(m,36,28,5,2,T.SNOW)
    for tx in range(52): m.set(tx,0,T.SNOW_TREE); m.set(tx,1,T.SNOW_TREE)
    for ty in range(48): m.set(50,ty,T.SNOW_TREE); m.set(51,ty,T.SNOW_TREE)
    # Boss odası
    for tx2 in range(30,50): m.set(tx2,36,T.STONE)
    for ty2 in range(36,46): m.set(30,ty2,T.STONE); m.set(49,ty2,T.STONE)
    m.set(39,36,T.DOOR); m.set(40,36,T.DOOR)
    _rect(m,31,37,18,8,T.ICE)
    # GEÇİŞLER
    _trans_strip(m,'x',2,  17,25, "desert",        57,27, T.SNOW,(-1,0))
    _trans_strip(m,'y',46,  4,12, "shadow_castle",  22,40, T.SNOW,(0,1))
    m.set(5, 6,T.CHEST); m.chests[(5,6)]   = ["hp_pot","mp_pot"]
    m.set(19, 6,T.CHEST); m.chests[(19,6)] = ["scout_coat","gold"]
    m.set(5, 19,T.CHEST); m.chests[(5,19)] = ["hp_pot","mp_pot"]
    m.set(38,42,T.CHEST); m.chests[(38,42)]= ["water_c","hp_pot","mp_pot","hp_pot"]
    def spirit_d(f):
        if f.get("water_crystal"): return ["dlg.spirit.1","dlg.spirit.2"]
        return ["dlg.spirit.3","dlg.spirit.4"]
    m.npcs.append(NPC(8,20,"npc.buz_ruhu",(180,220,255),spirit_d,"spirit"))
    m.enemies += [
        Enemy(5, 5,"ice_wolf",55,12,35,agro=5,loot=["gold"]),
        Enemy(20, 5,"ice_wolf",55,12,35,agro=5),
        Enemy(33, 5,"golem",  75,14,42,agro=4,loot=["hp_pot"]),
        Enemy(8, 19,"ice_wolf",60,13,38,agro=5),
        Enemy(22,22,"golem",  80,15,45,agro=4,loot=["mp_pot"]),
        Enemy(8, 34,"golem",  85,16,50,agro=4,loot=["hp_pot"]),
        Enemy(40,41,"golem", 180,25,120,agro=7,loot=["water_c"],is_boss=True),
    ]
    _snap_all(m); return m


def build_shadow_castle():
    m = GameMap(56, 52, "map.golge_kalesi", ambient=(40,0,60))
    _rect(m,0,0,56,52,T.SHADOW)
    _rect(m,2,2,52,48,T.FLOOR)
    # Bölme duvarları (geçilebilir kapılı)
    for tx in range(2,20): m.set(tx,18,T.WALL)
    for ty in range(18,34): m.set(2,ty,T.WALL); m.set(19,ty,T.WALL)
    m.set(10,18,T.DOOR); m.set(11,18,T.DOOR)
    m.set(10,33,T.DOOR); m.set(11,33,T.DOOR)
    for tx in range(36,54): m.set(tx,18,T.WALL)
    for ty in range(18,34): m.set(36,ty,T.WALL); m.set(53,ty,T.WALL)
    m.set(44,18,T.DOOR); m.set(45,18,T.DOOR)
    m.set(44,33,T.DOOR); m.set(45,33,T.DOOR)
    for tx in range(20,36): m.set(tx,22,T.WALL); m.set(tx,30,T.WALL)
    for ty in range(22,31): m.set(20,ty,T.WALL); m.set(35,ty,T.WALL)
    m.set(27,22,T.DOOR); m.set(28,22,T.DOOR)
    m.set(27,30,T.DOOR); m.set(28,30,T.DOOR)
    # GEÇİŞ
    _trans_strip(m,'x',2, 23,30, "ice_cave",  8,44, T.FLOOR,(-1,0))
    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["hp_pot","hp_pot","mp_pot"]
    m.set(48, 5,T.CHEST); m.chests[(48,5)] = ["warrior_crest","hp_pot"]
    m.set(5, 44,T.CHEST); m.chests[(5,44)] = ["hp_pot","hp_pot","steel_sword"]
    m.set(48,44,T.CHEST); m.chests[(48,44)]= ["mage_focus","elder_staff"]
    def king_d(f):
        if f.get("malachar_defeated"): return ["dlg.king.1","dlg.king.2"]
        return ["dlg.king.3","dlg.king.4","dlg.king.5"]
    m.npcs.append(NPC(10,8,"npc.kral_alderon",(200,160,80),king_d,"knight"))
    m.enemies += [
        Enemy(8, 8,"shadow_knight",100,20,65,agro=6,loot=["hp_pot","gold"]),
        Enemy(46, 8,"shadow_knight",100,20,65,agro=6,loot=["hp_pot"]),
        Enemy(8, 44,"shadow_knight",110,22,70,agro=6,loot=["mp_pot","gold"]),
        Enemy(46,44,"shadow_knight",110,22,70,agro=6,loot=["gold"]),
        Enemy(10,26,"shadow_knight",120,24,75,agro=7,loot=["hp_pot","mp_pot"]),
        Enemy(44,26,"shadow_knight",120,24,75,agro=7),
        Enemy(27,26,"malachar",500,35,999,agro=10,loot=["gold","gold"],is_boss=True),
    ]
    _snap_all(m); return m


def build_village_dungeon():
    m = GameMap(40, 34, "map.koy_alti_zindani", ambient=(10,5,20))
    _rect(m,0,0,40,34,T.STONE)
    for tx in range(40): m.set(tx,0,T.RUINS_WALL); m.set(tx,33,T.RUINS_WALL)
    for ty in range(34): m.set(0,ty,T.RUINS_WALL); m.set(39,ty,T.RUINS_WALL)
    _rect(m, 2, 2,16,12,T.FLOOR); _rect(m,22, 2,16,12,T.FLOOR)
    _rect(m, 2,18,16,14,T.FLOOR); _rect(m,22,18,16,14,T.FLOOR)
    _rect(m,17, 4, 6, 7,T.FLOOR); _rect(m,17,19, 6, 9,T.FLOOR)
    _rect(m, 5,13, 9, 5,T.FLOOR); _rect(m,26,13, 9, 5,T.FLOOR)
    for ty in range(34):
        for tx in range(40):
            if m.get(tx,ty)==T.STONE and any(m.get(tx+dx,ty+dy)==T.FLOOR for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                m.set(tx,ty,T.RUINS_WALL)
    # GEÇİŞ (oda içinden, kuzey)
    _trans_strip(m,'y',2,  7,12, "ashveil", 29,45, T.FLOOR,(0,-1))
    m.set(6, 5,T.CHEST); m.chests[(6,5)]   = ["hp_pot","mp_pot","gold"]
    m.set(30, 5,T.CHEST); m.chests[(30,5)] = ["steel_sword","leather_armor","gold"]
    m.set(6, 26,T.CHEST); m.chests[(6,26)] = ["arcane_staff","mage_robe"]
    m.set(30,26,T.CHEST); m.chests[(30,26)]= ["hp_pot","hp_pot","mp_pot","swift_boots"]
    m.enemies += [
        Enemy(12, 7,"skeleton",70,14,45,agro=5,loot=["gold","gold"]),
        Enemy(28, 6,"golem",  100,18,60,agro=4,loot=["hp_pot","gold"]),
        Enemy(8, 26,"skeleton",80,16,50,agro=5,loot=["mp_pot"]),
        Enemy(30,26,"golem",  110,20,65,agro=4,loot=["gold","gold"]),
        Enemy(20,22,"skeleton",90,17,55,agro=6,loot=["hp_pot","gold"]),
    ]
    _snap_all(m); return m


def build_south_meadow():
    m = GameMap(56, 42, "map.guney_cayiri")
    _rect(m,0,0,56,42,T.GRASS)
    _rect(m,5,10,20,14,T.FARMLAND); _rect(m,28,10,18,14,T.WHEAT)
    for tx in range(4,48): m.set(tx,9,T.FENCE); m.set(tx,25,T.FENCE)
    for ty in range(9,26): m.set(4,ty,T.FENCE); m.set(47,ty,T.FENCE)
    m.set(20,9,T.GRASS); m.set(21,9,T.GRASS)
    m.set(20,25,T.GRASS); m.set(21,25,T.GRASS)
    _room(m,5,28,14,10,T.WALL,T.FLOOR,"north")
    _room(m,22,28,10,8,T.WALL,T.FLOOR,"north")
    _path(m,20,0,20,10,T.DIRT,2); _path(m,5,22,52,22,T.DIRT,2)
    for ty in range(30,40):
        for tx in range(42,54):
            if (tx-48)**2+(ty-35)**2<22: m.set(tx,ty,T.WATER)
    for tx in range(56): m.set(tx,40,T.TREE); m.set(tx,41,T.TREE)
    for ty in range(42): m.set(55,ty,T.TREE)
    # GEÇİŞ
    _trans_strip(m,'y',2,  16,26, "ashveil",  22,49, T.GRASS,(0,-1))
    m.set(8, 30,T.CHEST); m.chests[(8,30)]  = ["farm_tool","hp_pot","gold"]
    m.set(46,22,T.CHEST); m.chests[(46,22)] = ["hp_pot","mana_gem"]
    def farmer_d(f): return ["dlg.farmer.1","dlg.farmer.2","dlg.farmer.3"]
    m.npcs.append(NPC(10,30,"npc.ciftci_torben",(160,120,80),farmer_d,"farmer"))
    def kid_d(f): return ["dlg.kid.1"]
    m.npcs.append(NPC(35,12,"npc.ciftlik_cocugu",(180,200,160),kid_d,"child"))
    def traveler_d(f): return ["dlg.traveler.1","dlg.traveler.2"]
    m.npcs.append(NPC(50,22,"npc.gezgin",(140,150,180),traveler_d,"traveler"))
    m.enemies += [
        Enemy(36, 4,"boar", 40, 9,25,agro=5,loot=["gold"]),
        Enemy(42, 6,"boar", 40, 9,25,agro=5),
        Enemy(8,  5,"slime",25, 5,15,agro=4,loot=["gold"]),
        Enemy(12, 5,"slime",25, 5,15,agro=4),
        Enemy(48,32,"wolf", 45,10,28,agro=5,loot=["hp_pot"]),
        Enemy(50,36,"wolf", 45,10,28,agro=5),
    ]
    _snap_all(m); return m


def build_west_river():
    m = GameMap(56, 42, "map.bati_nehri", ambient=(0,10,20))
    _rect(m,0,0,56,42,T.GRASS)
    for ty in range(42):
        for tx in range(25,31): m.set(tx,ty,T.RIVER)
    for tx in range(25,31):
        for ty in range(9,13):  m.set(tx,ty,T.BRIDGE)
        for ty in range(27,31): m.set(tx,ty,T.BRIDGE)
    _path(m,0,10,25,10,T.DIRT,2); _path(m,31,10,56,10,T.DIRT,2)
    _path(m,0,28,25,28,T.DIRT,2); _path(m,31,28,56,28,T.DIRT,2)
    _room(m,3,14,10,8,T.WALL,T.FLOOR,"east")
    for ty in range(0,8):
        for tx in range(0,10):
            if tx%3<2 and ty%3<2: m.set(tx,ty,T.TREE)
    for ty in range(33,42):
        for tx in range(35,56):
            if (tx-35)%3<2 and (ty-33)%3<2: m.set(tx,ty,T.TREE)
    # GEÇİŞLER
    _trans_strip(m,'x',54,18,28, "ashveil",  3,24, T.GRASS,(1,0))
    _trans_strip(m,'y',2, 24,32, "mystic_library",21, 4, T.GRASS,(0,-1))
    m.set(5, 16,T.CHEST); m.chests[(5,16)]  = ["river_gem","mp_pot","gold"]
    m.set(46,  5,T.CHEST); m.chests[(46,5)] = ["hp_pot","hp_pot","mana_gem"]
    m.set(46, 33,T.CHEST); m.chests[(46,33)]= ["fine_bow","gold"]
    def fisher_d(f):
        if f.get("sq_fish_done"): return ["dlg.fisher.1","dlg.fisher.2","dlg.fisher.3"]
        return ["dlg.fisher.4","dlg.fisher.5","dlg.fisher.6","dlg.fisher.7","dlg.fisher.8"]
    m.npcs.append(NPC(6,16,"npc.balikci_riva",(100,140,180),fisher_d,"fisher"))
    def hermit_d(f): return ["dlg.hermit.1","dlg.hermit.2"]
    m.npcs.append(NPC(44,4,"npc.munzevi",(180,160,200),hermit_d,"hermit"))
    m.enemies += [
        Enemy(18, 4,"slime",   30, 6,18,agro=4,loot=["gold"]),
        Enemy(40, 4,"goblin",  38, 8,22,agro=5,loot=["hp_pot"]),
        Enemy(14,34,"wolf",    42, 9,25,agro=5),
        Enemy(40,34,"goblin",  45,10,28,agro=5,loot=["gold"]),
        Enemy(36,18,"skeleton",50,11,30,agro=5,loot=["mp_pot"]),
        Enemy(40,22,"skeleton",50,11,30,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_mystic_library():
    m = GameMap(44, 38, "map.gizemli_kutuphane", ambient=(20,0,40))
    _rect(m,0,0,44,38,T.STONE)
    _rect(m,2,2,40,34,T.FLOOR)
    for tx in range(6,38,8):
        for ty in range(4,14): m.set(tx,ty,T.RUINS_WALL)
        m.set(tx,8,T.FLOOR); m.set(tx,9,T.FLOOR)
    for tx in range(6,38,8):
        for ty in range(22,34): m.set(tx,ty,T.RUINS_WALL)
        m.set(tx,28,T.FLOOR); m.set(tx,29,T.FLOOR)
    _rect(m,18,16,8,6,T.ICE)
    for tx in range(19,25): m.set(tx,17,T.FLOOR); m.set(tx,20,T.FLOOR)
    for ty in range(17,21): m.set(19,ty,T.FLOOR); m.set(24,ty,T.FLOOR)
    # GEÇİŞLER
    _trans_strip(m,'y',2, 18,26, "west_river",26, 3, T.FLOOR,(0,-1))
    _trans_strip(m,'y',36,18,26, "west_river",26, 4, T.FLOOR,(0,1))
    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["arcane_staff","mp_pot","gold"]
    m.set(37, 5,T.CHEST); m.chests[(37,5)] = ["mage_focus","mp_pot"]
    m.set(5, 30,T.CHEST); m.chests[(5,30)] = ["elder_staff","mp_pot","mp_pot"]
    m.set(37,30,T.CHEST); m.chests[(37,30)]= ["hp_pot","mp_pot","swift_boots","gold"]
    def libr_d(f):
        n=sum(1 for k in["sq_scroll1","sq_scroll2","sq_scroll3"] if f.get(k))
        if n>=3: return ["dlg.libr.1","dlg.libr.2","dlg.libr.3"]
        return ["dlg.libr.4",("dlg.libr.5",n),"dlg.libr.6"]
    m.npcs.append(NPC(21,19,"npc.kutuphaneci_elan",(140,100,200),libr_d,"scholar"))
    m.enemies += [
        Enemy(10, 8,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(28, 8,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(10,26,"golem",   90,16,52,agro=4,loot=["gold"]),
        Enemy(28,26,"golem",   90,16,52,agro=4,loot=["gold"]),
        Enemy(21,18,"skeleton",75,14,45,agro=6,loot=["mp_pot","gold"]),
    ]
    _snap_all(m); return m


# ─── UI ─────────────────────────────────────────────────────────
class UI:
    def __init__(self):
        # Sayısal/hizalı bilgi monospace kalır (sütunlar kaymasın),
        # başlıklar ve diyalog ortaçağ fontlarıyla çizilir.
        self.fsm=FontManager.get("mono",9)
        self.fss=FontManager.get("mono",11)
        self.fmd=FontManager.get("mono",14)
        self.flg=FontManager.get("title",22)
        self.fxl=FontManager.get("title",30)
        self.fti=FontManager.get("title",38)
        self.fdlg=FontManager.get("dialog",17)

    def txt(self,surf,text,x,y,col=UI_TX,fnt=None,shadow=True):
        f=fnt or self.fss
        if shadow: surf.blit(f.render(text,True,BK),(x+1,y+1))
        surf.blit(f.render(text,True,col),(x,y))

    def txt_c(self,surf,text,cx,y,col=UI_TX,fnt=None,shadow=True):
        """Metni cx merkezine göre ortalar — font genişliğinden bağımsız."""
        f=fnt or self.fss
        self.txt(surf,text,cx-f.size(text)[0]//2,y,col,f,shadow)

    # Degradeler her karede piksel piksel çizilmesin diye önbelleğe alınır.
    _bar_cache:Dict=dict()
    _panel_cache:Dict=dict()

    @classmethod
    def _bar_surface(cls,w,h,c1,c2):
        """Tam genişlikte degrade bar — dolu kısmı bundan kırpılarak çizilir."""
        key=(w,h,c1,c2)
        s=cls._bar_cache.get(key)
        if s is None:
            s=pygame.Surface((w,h))
            for i in range(w):
                tt=i/max(1,w-1)
                s.fill((int(c1[0]+(c2[0]-c1[0])*tt),int(c1[1]+(c2[1]-c1[1])*tt),
                        int(c1[2]+(c2[2]-c1[2])*tt)),(i,0,1,h))
            sh=pygame.Surface((w,h),pygame.SRCALPHA);sh.fill((255,255,255,20))
            s.blit(sh,(0,0))
            cls._bar_cache[key]=s
        return s

    def grad_bar(self,surf,x,y,w,h,val,mx,c1,c2,bg=(20,10,35)):
        pygame.draw.rect(surf,bg,(x,y,w,h))
        fill=int(w*max(0,val)/max(1,mx))
        if fill>0:
            surf.blit(self._bar_surface(w,h,tuple(c1),tuple(c2)),(x,y),pygame.Rect(0,0,fill,h))
        pygame.draw.rect(surf,UI_BD,(x,y,w,h),1)

    @classmethod
    def _panel_surface(cls,w,h,alpha):
        key=(w,h,alpha)
        s=cls._panel_cache.get(key)
        if s is None:
            s=pygame.Surface((w,h),pygame.SRCALPHA)
            for i in range(h):
                tt=i/max(1,h)
                s.fill((int(UI_BG[0]+4*tt),int(UI_BG[1]+2*tt),int(UI_BG[2]+12*tt),alpha),(0,i,w,1))
            pygame.draw.rect(s,UI_BD,(0,0,w,h),2)
            cls._panel_cache[key]=s
        return s

    def dim(self,surf,alpha=150):
        """Panel arkasindaki dunyayi karartir — metin okunakli kalsin."""
        ov=pygame.Surface((SW,SH),pygame.SRCALPHA);ov.fill((0,0,0,alpha));surf.blit(ov,(0,0))

    def panel(self,surf,x,y,w,h,alpha=220,glow=False):
        surf.blit(self._panel_surface(w,h,alpha),(x,y))
        if glow:
            gv=int(abs(math.sin(pygame.time.get_ticks()*0.002))*50)+20
            gs=pygame.Surface((w,h),pygame.SRCALPHA)
            pygame.draw.rect(gs,(*UI_AC,gv),(0,0,w,h),3)
            surf.blit(gs,(x,y))

    def draw_stat_alloc(self,surf,stats,free,sel,is_lu=False,tick=0):
        self.dim(surf)
        pw,ph=510,430;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        title=T_("stat_levelup") if is_lu else T_("stat_alloc")
        col=UI_GD if is_lu else UI_AC
        self.txt_c(surf,title,px+pw//2,py+12,col,self.flg)
        self.txt(surf,f"{'Kalan:'+str(free)+' puan' if is_lu else '10 puan harca. Kalan:'+str(free)}",px+18,py+42,LGR,self.fss)
        stat_cols={"str":HP_R,"int":UI_BL,"agi":UI_GN,"vit":UI_GD,"wis":UI_PR}
        for si,(sk,sname) in enumerate(STAT_NAMES):
            val=getattr(stats,sk if sk!="int" else "int_")
            eq_b=stats._equip_bonus(sk)
            sel_this=(si==sel);sy2=py+76+si*62
            rs=pygame.Surface((pw-24,54),pygame.SRCALPHA)
            rs.fill((*UI_AC,45) if sel_this else (*UI_BD,18))
            if sel_this: pygame.draw.rect(rs,UI_AC,(0,0,pw-24,54),2)
            surf.blit(rs,(px+12,sy2))
            sc2=stat_cols.get(sk,UI_TX)
            self.txt(surf,stat_name(sk),px+20,sy2+6,sc2,self.fmd)
            self.txt(surf,stat_desc(sk),px+20,sy2+26,GR,self.fsm)
            self.txt(surf,"[<]",px+pw-140,sy2+12,(200,100,100) if val>2 else GR,self.fmd)
            self.txt(surf,str(val),px+pw-100,sy2+12,WH,self.flg)
            if eq_b>0: self.txt(surf,f"+{eq_b}",px+pw-75,sy2+18,UI_GN,self.fsm)
            self.txt(surf,"[>]",px+pw-56,sy2+12,(100,200,100) if free>0 else GR,self.fmd)
            self.grad_bar(surf,px+165,sy2+18,180,11,val+eq_b,25,(20,10,40),sc2)
        self.txt(surf,T_("ui.stat_keys"),px+16,py+ph-24,GR,self.fsm)

    def draw_class_select(self,surf,sel,tick):
        surf.fill(DKG)
        for i in range(120):
            random.seed(i*137+42);sx2=random.randint(0,SW);sy2=random.randint(0,SH//2);br=random.randint(60,180)
            pygame.draw.circle(surf,(br,br,br),(sx2,sy2),1)
        random.seed()
        self.txt_c(surf,T_("class_select"),SW//2,26,UI_AC,self.fxl)
        self.txt_c(surf,T_("class_subtitle"),SW//2,62,LGR,self.fmd)
        keys=list(CLASS_INFO.keys());cw,ch2=210,320;gap=8;total_w=(cw+gap)*4-gap;start_x=SW//2-total_w//2
        for i,k in enumerate(keys):
            ci=CLASS_INFO[k];cc=CLASS_COL[k];cx2=start_x+i*(cw+gap);cy2=96;sel_this=(i==sel)
            cs=pygame.Surface((cw,ch2),pygame.SRCALPHA)
            if sel_this:
                gv=int(abs(math.sin(tick*0.003))*35)+35;cs.fill((*cc,20+gv));pygame.draw.rect(cs,cc,(0,0,cw,ch2),3)
            else:
                cs.fill((*UI_BG,195));pygame.draw.rect(cs,(*cc,70),(0,0,cw,ch2),2)
            surf.blit(cs,(cx2,cy2))
            sp=PA.player_surf("down",tick//50,k);surf.blit(pygame.transform.scale(sp,(60,60)),(cx2+cw//2-30,cy2+8))
            nm=self.fmd.render(class_text(k,"name"),True,cc if sel_this else LGR);surf.blit(nm,(cx2+cw//2-nm.get_width()//2,cy2+74))
            # Saldırı türü
            self.txt(surf,T_("ui.atk_prefix")+class_text(k,"atk_name")[:12],cx2+6,cy2+96,UI_GD if sel_this else GR,self.fsm,shadow=False)
            # Stat çubukları
            bonus=ci["bonus"]
            stat_labels=[(T_("ui.abbr_str"),"str",HP_R),(T_("ui.abbr_int"),"int",UI_BL),(T_("ui.abbr_agi"),"agi",UI_GN),(T_("ui.abbr_vit"),"vit",UI_GD),(T_("ui.abbr_wis"),"wis",UI_PR)]
            for si2,(slbl,sk,scol) in enumerate(stat_labels):
                sv=2+bonus.get(sk,0)
                self.txt(surf,slbl,cx2+6,cy2+112+si2*22,LGR,self.fsm,shadow=False)
                self.grad_bar(surf,cx2+40,cy2+112+si2*22,cw-48,9,sv,12,(20,10,40),scol)
            for li,ln in enumerate(class_text(k,"lore").split("\n")):
                self.txt(surf,ln,cx2+6,cy2+236+li*16,(*cc,200) if sel_this else GR,self.fsm,shadow=False)
        pv=int(abs(math.sin(tick*0.003))*80)+120
        self.txt(surf,T_("class_confirm"),SW//2-140,SH-38,(int(pv),100,255),self.fmd)

    def draw_story(self,surf,lines_shown,tick):
        surf.fill(DKG)
        for i in range(80):
            random.seed(i*251);sx2=random.randint(0,SW);sy2=random.randint(0,SH);br=random.randint(50,160)
            pygame.draw.circle(surf,(br,br,br),(sx2,sy2),1)
        random.seed()
        self.txt_c(surf,TITLE,SW//2,36,UI_AC,self.fxl)
        for i,(line,col) in enumerate(STORY_LINES[:lines_shown]):
            line=T_("story.%d"%(i+1),default=line) if line.strip() else line
            y=130+i*30
            if line==" " or y>SH-50: continue
            ts=self.fmd.render(line,True,col);surf.blit(ts,(SW//2-ts.get_width()//2,y))
        if lines_shown>=len(STORY_LINES):
            pv=int(abs(math.sin(tick*0.003))*80)+120
            self.txt_c(surf,T_("ui.story_next"),SW//2,SH-60,(int(pv),120,255),self.flg)

    def draw_title(self,surf,tick):
        surf.fill(DKG)
        for i in range(150):
            random.seed(i*137);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.001+i*0.3))*100)+80
            br=(min(255,pv//2),min(255,pv//3),min(255,pv));pygame.draw.circle(surf,br,(sx2,sy2),1)
        random.seed()
        tt=self.fti.render(TITLE,True,UI_AC)
        surf.blit(self.fti.render(TITLE,True,(50,30,80)),(SW//2-tt.get_width()//2+3,143));surf.blit(tt,(SW//2-tt.get_width()//2,140))
        self.txt_c(surf,"v%s — %s"%(VERSION,T_("ui.tagline")),SW//2,190,UI_GD,self.fmd)
        for i2,cls in enumerate(CLASS_INFO.keys()):
            sp=PA.player_surf("down",tick//50,cls);surf.blit(pygame.transform.scale(sp,(56,56)),(SW//2-112+i2*56,240))
        pv2=int(abs(math.sin(tick*0.003))*80)+120
        btn=pygame.Surface((300,42),pygame.SRCALPHA);btn.fill((*UI_BD,90));pygame.draw.rect(btn,UI_AC,(0,0,300,42),2);surf.blit(btn,(SW//2-150,320))
        self.txt_c(surf,T_("title_play"),SW//2,330,(int(pv2*0.8),100,255),self.fmd)
        if has_save():
            self.txt_c(surf,T_("ui.title_continue"),SW//2,368,(120,220,160),self.fmd)
            self.txt_c(surf,T_("title_settings"),SW//2,396,UI_GD,self.fss)
            self.txt_c(surf,"WASD Hareket  E Konus  Spc Saldiri  1-4 Yetenek  I Envanter  ESC Cikis",SW//2,418,GR,self.fsm)
            return
        self.txt_c(surf,T_("title_settings"),SW//2,368,UI_GD,self.fss)
        self.txt_c(surf,"WASD Hareket  E Konus  Spc Saldiri  1-4 Yetenek  I Envanter  ESC Cikis",SW//2,390,GR,self.fsm)

    def draw_levelup_popup(self,surf,level,tick):
        pw,ph=380,76;px=SW//2-pw//2;py=100
        s=pygame.Surface((pw,ph),pygame.SRCALPHA);s.fill((25,15,45,215))
        gv=int(abs(math.sin(tick*0.004))*40)+40;pygame.draw.rect(s,(*UI_GD,gv+100),(0,0,pw,ph),3)
        tt=self.flg.render(T_("ui.level_up_n",level),True,UI_GD);s.blit(tt,(pw//2-tt.get_width()//2,8))
        t2=self.fss.render(T_("ui.levelup_hint"),True,UI_TX);s.blit(t2,(pw//2-t2.get_width()//2,38))
        surf.blit(s,(px,py))

    def draw_gameover(self,surf):
        self.dim(surf,200)
        self.txt_c(surf,T_("gameover_title"),SW//2,SH//2-70,HP_R,self.fxl)
        self.txt(surf,T_("gameover_sub"),SW//2-120,SH//2-10,LGR,self.fmd)
        self.txt(surf,T_("gameover_restart"),SW//2-100,SH//2+40,UI_AC,self.fmd)

    def draw_victory(self,surf,tick):
        surf.fill(DKG)
        for i in range(200):
            random.seed(i*313);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.002+i*0.5))*120)+80;pygame.draw.circle(surf,(pv,int(pv*0.8),50),(sx2,sy2),1)
        random.seed()
        gv=int(abs(math.sin(tick*0.002))*60)+80
        self.txt_c(surf,T_("victory_title"),SW//2,120,(255,gv+80,gv//2),self.fti)
        self.txt_c(surf,T_("victory_sub"),SW//2,200,UI_GD,self.fxl)
        self.txt_c(surf,T_("victory_sub2"),SW//2,260,UI_TX,self.flg)
        self.txt(surf,T_("victory_menu"),SW//2-100,380,(int(abs(math.sin(tick*0.003))*100)+120,100,255),self.fmd)

    def draw_transition(self,surf,alpha,name):
        ov=pygame.Surface((SW,SH),pygame.SRCALPHA);ov.fill((0,0,0,min(255,alpha)));surf.blit(ov,(0,0))
        if alpha>120:
            t=self.flg.render(name,True,UI_AC);t.set_alpha(min(255,alpha*2-240));surf.blit(t,(SW//2-t.get_width()//2,SH//2-16))

    CHAPTER_BANNER_H = 92   # duyuru yalnızca bu yüksekliği kaplar

    def draw_chapter(self,surf,chapter,alpha):
        """Bölüm duyurusu — üst şeritte. Eskiden ekranın ortasını 4 sn kapatıyordu."""
        if chapter not in QUESTS: return
        a=min(255,alpha);bh=self.CHAPTER_BANNER_H
        band=pygame.Surface((SW,bh),pygame.SRCALPHA)
        band.fill((0,0,0,min(170,a)))
        pygame.draw.line(band,(*UI_GD,min(200,a)),(0,bh-1),(SW,bh-1),2)
        surf.blit(band,(0,0))
        t=self.fxl.render(f"{T_('chapter_label')} {chapter}",True,UI_GD)
        t.set_alpha(a);surf.blit(t,(SW//2-t.get_width()//2,10))
        t2=self.flg.render(quest_title(chapter),True,UI_AC)
        t2.set_alpha(a);surf.blit(t2,(SW//2-t2.get_width()//2,52))

    def draw_ability_bar(self,surf,stats,tick):
        ab_list=ABILITIES.get(stats.char_class,[])
        if not ab_list: return
        slot_w=54;bar_w=slot_w*4+8;bar_h=62
        bx=SW//2-bar_w//2;by=SH-bar_h-6
        self.panel(surf,bx-2,by-2,bar_w+4,bar_h+4)
        for i,ab in enumerate(ab_list):
            sx=bx+i*slot_w;sy=by
            locked=stats.level<ab["level"]
            on_cd=stats.ab_cds[i]>0
            no_mp=stats.mp<ab["mp"]
            col=ab["col"]
            ss=pygame.Surface((slot_w-2,bar_h),pygame.SRCALPHA)
            if locked:   ss.fill((25,15,35,200))
            elif on_cd:  ss.fill((18,12,28,200))
            else:        ss.fill((*col,55))
            pygame.draw.rect(ss,col if not locked else GR,(0,0,slot_w-2,bar_h),2)
            surf.blit(ss,(sx,sy))
            # Tuş etiketi
            self.txt(surf,str(i+1),sx+3,sy+2,UI_GD if not locked else GR,self.fsm,shadow=False)
            # İkon dairesi
            pygame.draw.circle(surf,col if not locked else GR,(sx+slot_w//2-1,sy+21),11)
            if not locked: pygame.draw.circle(surf,WH,(sx+slot_w//2-1,sy+21),11,1)
            # Cooldown overlay
            if on_cd:
                max_cd=ab["cd"]; frac=stats.ab_cds[i]/max(1,max_cd)
                cd_s=pygame.Surface((24,24),pygame.SRCALPHA)
                pygame.draw.circle(cd_s,(0,0,0,160),(12,12),11)
                ang2=int(360*frac)
                if ang2>0:
                    pygame.draw.arc(cd_s,(255,255,255,180),(1,1,22,22),
                        math.radians(90),math.radians(90+ang2),4)
                surf.blit(cd_s,(sx+slot_w//2-13,sy+9))
                cd_n=stats.ab_cds[i]//FPS+1
                ct=self.fsm.render(str(cd_n),True,WH)
                surf.blit(ct,(sx+slot_w//2-1-ct.get_width()//2,sy+16))
            # İsim
            c2=GR if locked else(UI_TX if not on_cd else GR)
            self.txt(surf,ability_name(ab)[:7],sx+1,sy+36,c2,self.fsm,shadow=False)
            # MP maliyeti
            mc=UI_RD if(no_mp and not locked) else GR
            self.txt(surf,f"MP:{ab['mp']}",sx+1,sy+48,mc,self.fsm,shadow=False)
            # Kilit seviyesi
            if locked:
                lk=self.fsm.render(f"Sv{ab['level']}",True,(160,80,80))
                surf.blit(lk,(sx+slot_w//2-1-lk.get_width()//2,sy+17))

    def draw_quest_marker(self,surf,tx,ty,cx,cy,tick):
        """NPC'nin üstünde altın sarısı ünlem — işi olan NPC belli olsun."""
        sx=tx*TILE-cx+TILE//2;sy=ty*TILE-cy-26
        if not(-20<=sx<SW+20 and -20<=sy<SH): return
        bob=int(abs(math.sin(tick*0.004))*4)
        t=self.fmd.render("!",True,UI_GD)
        sh=self.fmd.render("!",True,(60,40,10))
        surf.blit(sh,(sx-t.get_width()//2+1,sy-bob+1))
        surf.blit(t,(sx-t.get_width()//2,sy-bob))

    def draw_interact_badge(self,surf,tx,ty,cx,cy,tick):
        """Etkileşilebilir hedefin üstünde yanıp sönen [E] rozeti."""
        sx=tx*TILE-cx+TILE//2;sy=ty*TILE-cy-20
        if not(0<=sx<SW and 0<=sy<SH): return
        pulse=int(abs(math.sin(tick*0.006))*60)+150
        t=self.fsm.render("[E]",True,(255,240,160))
        bg=pygame.Surface((t.get_width()+8,t.get_height()+4),pygame.SRCALPHA)
        bg.fill((20,10,35,190));pygame.draw.rect(bg,(pulse,pulse//2,60),bg.get_rect(),1)
        bob=int(abs(math.sin(tick*0.005))*3)
        surf.blit(bg,(sx-bg.get_width()//2,sy-bob))
        surf.blit(t,(sx-t.get_width()//2,sy+2-bob))

    def draw_dialog(self,surf,npc_name,lines,page,total,revealed=None):
        """revealed: gösterilecek harf sayısı (daktilo etkisi); None = hepsi."""
        bh=112;bx=8;by=SH-bh-8
        self.panel(surf,bx,by,SW-16,bh,glow=True)
        pygame.draw.rect(surf,UI_BD,(bx,by-2,self.fmd.size(npc_name)[0]+16,18))
        self.txt(surf,npc_name,bx+8,by,UI_AC,self.fmd,shadow=False)
        left=10**9 if revealed is None else revealed
        done=True
        for i,line in enumerate(lines[:4]):
            if left<=0: done=False;break
            shown=line if len(line)<=left else line[:left]
            left-=len(line)
            if len(shown)<len(line): done=False
            col=UI_GD if line.startswith("[") else UI_TX
            self.txt(surf,shown,bx+14,by+20+i*21,col,self.fdlg)
        if done and(pygame.time.get_ticks()//600)%2==0:
            self.txt(surf,T_("dialog_continue"),SW-130,by+bh-20,UI_AC,self.fsm)
        if total>1: self.txt(surf,f"{page}/{total}",SW-50,by+4,GR,self.fsm)

    def draw_inventory(self,surf,player,sel,eq_tab,tick,eq_sel=0):
        self.dim(surf)
        pw,ph=640,440;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        # Sekmeler
        # Sekme başlıkları: pasif olanın üstünde [TAB] rozeti — hangi tuşla
        # geçileceği ekranda görünsün diye (aksi halde keşfedilmiyor).
        tw=138
        for i,(tname,tcol) in enumerate([(T_("equip_tab"),UI_TX),(T_("gear_tab"),UI_GD)]):
            active=(i==eq_tab)
            tx0=px+16+i*(tw+6)
            ts=pygame.Surface((tw,26),pygame.SRCALPHA)
            ts.fill((*UI_AC,80) if active else (*UI_BD,30))
            pygame.draw.rect(ts,UI_AC if active else UI_BD,(0,0,tw,26),2)
            surf.blit(ts,(tx0,py+8))
            self.txt(surf,tname,tx0+8,py+12,UI_AC if active else GR,self.fss,shadow=False)
            if not active:
                pulse=int(abs(math.sin(tick*0.005))*80)+140
                badge=self.fsm.render("[TAB]",True,(pulse,pulse,120))
                surf.blit(badge,(tx0+tw-badge.get_width()-6,py+14))
        self.txt(surf,f"{T_('gold')}:{player.stats.gold}",px+pw-120,py+10,UI_GD,self.fmd)

        if eq_tab==0:
            # Eşya sekmesi
            unique:Dict={}
            for k in player.inventory: unique[k]=unique.get(k,0)+1
            all_keys=list(unique.keys())
            for i,(k,cnt) in enumerate(unique.items()):
                itm=ALL_ITEMS.get(k)
                if not itm: continue
                row,col2=divmod(i,5);ix=px+14+col2*120;iy=py+44+row*90
                if iy+90>py+ph-30: break
                sel_this=(i==sel)
                ss=pygame.Surface((116,86),pygame.SRCALPHA)
                ss.fill((*UI_AC,70) if sel_this else (*UI_BD,28))
                pygame.draw.rect(ss,UI_AC if sel_this else UI_BD,(0,0,116,86),2)
                surf.blit(ss,(ix,iy))
                ic2=itm[1];pygame.draw.rect(surf,ic2,(ix+8,iy+8,40,40))
                pygame.draw.rect(surf,WH,(ix+8,iy+8,40,40),1)
                if itm[2]=="equip":
                    eic=PA.equip_icon(itm[3],ic2);surf.blit(eic,(ix+10,iy+10))
                self.txt(surf,item_name(k)[:10],ix+4,iy+52,WH,self.fsm)
                if cnt>1: self.txt(surf,f"x{cnt}",ix+96,iy+8,UI_GD,self.fsm)
                if itm[2]=="equip" and k in player.stats.equipment.values():
                    ep=pygame.Surface((116,86),pygame.SRCALPHA)
                    ep.fill((40,200,80,35));pygame.draw.rect(ep,(40,200,80,120),(0,0,116,86),3)
                    surf.blit(ep,(ix,iy))
                    self.txt(surf,T_("equipped"),ix+56,iy+8,UI_GN,self.fsm)
            if 0<=sel<len(all_keys):
                si=ALL_ITEMS.get(all_keys[sel])
                if si:
                    self.txt(surf,item_name(all_keys[sel]),px+14,py+ph-62,UI_AC,self.fmd)
                    self.txt(surf,item_desc(all_keys[sel]),px+14,py+ph-44,LGR,self.fss)
                    if si[2]=="equip":
                        ek=all_keys[sel]; slot2=EQUIP_ITEMS[ek][3]
                        cur=player.stats.equipment.get(slot2)
                        if cur==ek: self.txt(surf,T_("item_unequip"),px+14,py+ph-26,UI_RD,self.fss)
                        else:       self.txt(surf,f"{T_('item_equip')} ({slot2})",px+14,py+ph-26,UI_GN,self.fss)
                    elif si[2] in("heal","mana"):
                        self.txt(surf,T_("item_use"),px+14,py+ph-26,UI_GN,self.fss)
        else:
            # Ekipman sekmesi — her yuva ayrı satır (5 yuva)
            st=player.stats
            rh=66
            for si2,slot in enumerate(EQUIP_SLOTS):
                sname=T_("slot_"+slot);scol=SLOT_COLORS[slot]
                iy=py+44+si2*(rh+4)
                is_sel=(si2==eq_sel)
                ss=pygame.Surface((pw-28,rh),pygame.SRCALPHA)
                ss.fill((*UI_BD,60 if is_sel else 25))
                pygame.draw.rect(ss,UI_AC if is_sel else scol,(0,0,pw-28,rh),3 if is_sel else 2)
                surf.blit(ss,(px+14,iy))
                if is_sel:
                    self.txt(surf,">",px+2,iy+rh//2-8,UI_AC,self.fmd)
                eic2=PA.equip_icon(slot,scol);surf.blit(eic2,(px+20,iy+14))
                self.txt(surf,sname,px+64,iy+6,scol,self.fmd)
                ik=st.equipment.get(slot)
                if ik and ik in EQUIP_ITEMS:
                    edata=EQUIP_ITEMS[ik]
                    self.txt(surf,item_name(ik),px+180,iy+8,WH,self.fss)
                    bonus_str=" | ".join(f"{k2.upper()}+{v}" for k2,v in edata[2].items())
                    self.txt(surf,bonus_str,px+180,iy+28,UI_GN,self.fsm)
                    if is_sel: self.txt(surf,T_("item_unequip"),px+180,iy+46,UI_RD,self.fsm)
                else:
                    self.txt(surf,T_("slot_empty"),px+180,iy+16,GR,self.fss)
                    if is_sel: self.txt(surf,T_("slot_hint"),px+180,iy+38,GR,self.fsm)
            # Ekipman bonusu
            self.txt(surf,T_("ui.equip_bonus"),px+14,py+ph-56,UI_GD,self.fss)
            stats_show=[("str",HP_R),("int",UI_BL),("agi",UI_GN),("vit",UI_GD),("wis",UI_PR)]
            for si3,(sk,sc) in enumerate(stats_show):
                b=st._equip_bonus(sk)
                if b>0: self.txt(surf,f"+{b}{sk.upper()}",px+14+si3*80,py+ph-36,sc,self.fsm)
        hint=(T_("ui.inv_keys_items") if eq_tab==0
              else T_("ui.inv_keys_gear"))
        self.txt(surf,hint,px+14,py+ph-12,GR,self.fsm)

    PAUSE_OPTS=[
        (T_("ui.pause_resume"),   (100,220,100)),
        (T_("ui.pause_save"),  (120,200,240)),
        (T_("ui.pause_settings"), (180,140,250)),
        (T_("ui.pause_menu"),(220,150,60)),
        (T_("ui.pause_quit"),   (220,80,80)),
    ]

    def draw_pause(self,surf,tick,pause_sel=0):
        """ESC ile açılan duraklama menüsü."""
        self.dim(surf,160)
        pw,ph=360,270; px=SW//2-pw//2; py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt_c(surf,T_("ui.paused"),px+pw//2,py+14,UI_AC,self.flg)
        for i,(label,col) in enumerate(self.PAUSE_OPTS):
            oy=py+58+i*40
            sel_this=(i==pause_sel)
            ss=pygame.Surface((pw-28,34),pygame.SRCALPHA)
            ss.fill((*col,70 if sel_this else 25))
            pygame.draw.rect(ss,col if sel_this else (*col[:3],80),(0,0,pw-28,34),2 if sel_this else 1)
            surf.blit(ss,(px+14,oy))
            self.txt_c(surf,label,px+pw//2,oy+7,col if sel_this else LGR,self.fmd)

    def draw_settings(self,surf,sel,tick):
        """Ayarlar paneli."""
        pw,ph=480,360;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt_c(surf,T_("settings"),px+pw//2,py+12,UI_AC,self.flg)

        opts=[
            (T_("set_fullscreen"), T_("set_on") if CFG.fullscreen else T_("set_off"), "fullscreen"),
            (T_("set_master"),     f"%d%%" % CFG.master_vol,  "master_vol"),
            (T_("set_sfx"),        f"%d%%" % CFG.sfx_vol,     "sfx_vol"),
            (T_("set_music"),      f"%d%%" % CFG.music_vol,   "music_vol"),
            (T_("set_language"),   Locale.label(Locale.current()),  "language"),
            (T_("set_fps"),        T_("set_on") if CFG.show_fps else T_("set_off"), "show_fps"),
        ]
        for i,(label,val,_) in enumerate(opts):
            oy=py+56+i*44
            sel_this=(i==sel)
            rs=pygame.Surface((pw-24,38),pygame.SRCALPHA)
            rs.fill((*UI_AC,50) if sel_this else (*UI_BD,20))
            if sel_this: pygame.draw.rect(rs,UI_AC,(0,0,pw-24,38),2)
            surf.blit(rs,(px+12,oy))
            self.txt(surf,label,px+20,oy+10,UI_AC if sel_this else LGR,self.fss)
            vt=self.fss.render(val,True,UI_GD if sel_this else GR)
            surf.blit(vt,(px+pw-vt.get_width()-22,oy+10))
            if sel_this:
                self.txt(surf,"<",px+pw-vt.get_width()-42,oy+10,(180,80,80),self.fss)
                self.txt(surf,">",px+pw-10,oy+10,(80,180,80),self.fss)

        self.txt(surf,T_("set_back"),px+16,py+ph-28,GR,self.fss)

    def draw_mini_quests(self,surf,flags,player_cls):
        """Yan panel: devam eden yan görevler (en fazla 4 tanesi)."""
        rows=[]
        for sq in SIDE_QUESTS:
            got,need=sq["progress"](flags)
            if got>=need:
                if not flags.get("sqpaid_"+sq["id"]): continue
                continue          # bitenler panelde yer kaplamasın
            unit=T_(sq["unit"])
            rows.append((T_(sq["title"]),"%d/%d %s"%(got,need,unit),sq["col"]))
        done_n=sum(1 for sq in SIDE_QUESTS if sq_done(sq,flags))
        rows=rows[:4]
        if not rows and not done_n: return
        pw=214;row_h=22;ph=32+len(rows)*row_h
        px=SW-pw-6;py=SH//2-ph//2-40
        self.panel(surf,px,py,pw,ph)
        self.txt(surf,T_("ui.side_quests"),px+8,py+4,UI_GD,self.fsm)
        self.txt(surf,"%d/%d"%(done_n,len(SIDE_QUESTS)),px+pw-40,py+4,UI_GN,self.fsm)
        for i,(qn,qv,qc) in enumerate(rows):
            self.txt(surf,"• "+qn,px+8,py+18+i*row_h,LGR,self.fsm)
            self.txt(surf,qv,px+pw-self.fsm.size(qv)[0]-8,py+18+i*row_h,qc,self.fsm)

    def draw_hud(self,surf,player,map_name,chapter,quest_name,tick):
        st=player.stats;cc=CLASS_COL.get(st.char_class,(100,100,200))
        ci=CLASS_INFO[st.char_class]
        # Sol panel (270x130)
        self.panel(surf,6,6,270,130)
        pygame.draw.rect(surf,cc,(10,10,3,118))
        self.txt(surf,f"{class_text(st.char_class,'name')}  {T_('lvl')}{st.level}",18,10,cc,self.fmd)
        self.txt(surf,"HP",18,30,HP_G,self.fsm)
        self.grad_bar(surf,36,30,226,10,st.hp,st.max_hp,(80,15,15),HP_G)
        self.txt(surf,f"{st.hp}/{st.max_hp}",38,31,(220,255,220),self.fsm)
        self.txt(surf,"MP",18,44,MP_B,self.fsm)
        self.grad_bar(surf,36,44,226,10,st.mp,st.max_mp,(10,15,60),UI_CY)
        self.txt(surf,f"{st.mp}/{st.max_mp}",38,45,(180,220,255),self.fsm)
        self.txt(surf,"XP",18,58,XP_T,self.fsm)
        self.grad_bar(surf,36,58,226,8,st.xp,st.xp_next,(15,45,35),XP_T)
        self.txt(surf,f"ATK:{st.attack}  DEF:{st.defense}  AGI:{st.agi+st._equip_bonus('agi')}",18,72,LGR,self.fsm)
        gp=int(abs(math.sin(tick*0.003))*15)
        self.txt(surf,f"{T_('gold')}:{st.gold}",18,86,(230+gp,180,40),self.fsm)
        if st.skill_points>0:
            sc=(255,220,50) if (tick//500)%2==0 else (200,160,30)
            self.txt(surf,f"[U]+{st.skill_points} {T_('skill_pts')}",140,86,sc,self.fsm)
        by=102
        if "war_cry" in st.buffs:      self.txt(surf,T_("ui.buff_war_cry"),18,by,(255,120,50),self.fsm)
        elif "holy_shield" in st.buffs:self.txt(surf,T_("ui.buff_holy"), 18,by,(255,220,60),self.fsm)
        eq_strs=[]
        for slot,ik in st.equipment.items():
            if ik and ik in EQUIP_ITEMS: eq_strs.append(item_name(ik)[:8])
        if eq_strs:
            eq_y=by if "war_cry" not in st.buffs and "holy_shield" not in st.buffs else by+14
            self.txt(surf,"  ".join(eq_strs[:2]),18,eq_y,(100,120,160),self.fsm)
        # Üst merkez
        mn=self.fmd.render(map_name,True,UI_AC)
        surf.blit(mn,(SW//2-mn.get_width()//2,6))
        qn=f"{T_('chapter_label')} {chapter}: {quest_name[:30]}"
        qt=self.fsm.render(qn,True,UI_GD)
        surf.blit(qt,(SW//2-qt.get_width()//2,26))
        atk_name=class_text(st.char_class,"atk_name")
        at=self.fsm.render(f"{T_('atk_label')} {atk_name}",True,(120,160,120))
        surf.blit(at,(SW//2-at.get_width()//2,42))
        # Sağ üst kontroller
        tips=[T_("ui.key_move"),T_("ui.key_interact"),T_("ui.key_attack"),T_("ui.key_ability"),T_("ui.key_inventory"),T_("ui.key_quests"),T_("ui.key_settings"),T_("ui.key_fullscreen")]
        for i,tip in enumerate(tips):
            t2=self.fsm.render(tip,True,(55,65,75))
            surf.blit(t2,(SW-t2.get_width()-6,8+i*13))

    def draw_quest_log(self,surf,flags,chapter):
        """İki sütun: solda ana hikâye bölümleri, sağda yan görevler.

        Yan görev sayısı 3'ten 8'e çıkınca tek sütuna sığmıyordu.
        """
        self.dim(surf)
        pw,ph=740,420;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt(surf,T_("quest_log"),px+16,py+8,UI_GD,self.flg)
        colw=(pw-44)//2
        lx=px+16;rx=px+28+colw
        pygame.draw.line(surf,(*UI_BD,140),(rx-10,py+46),(rx-10,py+ph-30),1)

        # ── Sol sütun: ana görev zinciri ─────────────────────────
        y=py+48
        for ch in QUESTS:
            if ch<chapter:
                pygame.draw.rect(surf,(*UI_GN,28),(lx-4,y-2,colw,30))
                self.txt(surf,"[✓] %s %d: %s"%(T_("chapter_label"),ch,quest_title(ch)),lx,y,UI_GN,self.fsm)
                self.txt(surf,"    "+T_("quest_done"),lx,y+14,GR,self.fsm)
            elif ch==chapter:
                pv=int(abs(math.sin(pygame.time.get_ticks()*0.003))*25)
                pygame.draw.rect(surf,(*UI_GD,38+pv),(lx-4,y-2,colw,34))
                pygame.draw.rect(surf,UI_GD,(lx-4,y-2,colw,34),2)
                self.txt(surf,"[►] %s %d: %s"%(T_("chapter_label"),ch,quest_title(ch)),lx,y,UI_GD,self.fss)
                self.txt(surf,"    "+quest_desc(ch),lx,y+16,UI_TX,self.fsm)
            else:
                self.txt(surf,"[?] %s %d: ???"%(T_("chapter_label"),ch),lx,y,(55,55,65),self.fsm)
            y+=36

        # ── Sağ sütun: yan görevler (tablodan) ───────────────────
        done_n=sum(1 for sq in SIDE_QUESTS if sq_done(sq,flags))
        self.txt(surf,T_("ui.side_quests_hdr"),rx,py+48,UI_PR,self.fsm)
        self.txt(surf,"%d/%d"%(done_n,len(SIDE_QUESTS)),rx+colw-36,py+48,UI_GN,self.fsm)
        y=py+68
        for sq in SIDE_QUESTS:
            got,need=sq["progress"](flags)
            done=got>=need
            sym="✓" if done else "○"
            self.txt(surf,"[%s] %s"%(sym,T_(sq["title"])),rx,y,UI_GN if done else LGR,self.fsm)
            if done:
                self.txt(surf,T_("ui.completed"),rx+colw-70,y,UI_GN,self.fsm)
                y+=18
            else:
                self.txt(surf,"%d/%d"%(got,need),rx+colw-36,y,sq["col"],self.fsm)
                self.txt(surf,"  "+T_(sq["desc"]),rx,y+12,GR,self.fsm)
                self.txt(surf,"  +%d %s  +%d XP"%(sq["gold"],T_("gold"),sq["xp"]),rx,y+24,UI_GD,self.fsm)
                y+=40
            if y>py+ph-40: break
        self.txt(surf,T_("ui.close_quests"),px+14,py+ph-20,GR,self.fsm)


# ─── Game ────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        SoundManager.init()
        FontManager.set_language(Locale.current())
        self._set_app_id()
        flags=pygame.FULLSCREEN if CFG.fullscreen else 0
        self.screen=pygame.display.set_mode((SW,SH),flags)
        pygame.display.set_caption(TITLE)
        self._set_window_icon()
        self.clock=pygame.time.Clock()
        self.ui=UI(); self.ps=PS()
        self.fps_font=pygame.font.SysFont("monospace",12,bold=True)
        self._reset()

    @staticmethod
    def _set_app_id():
        """Windows görev çubuğu ikonu.

        Kimlik ayarlanmazsa Windows pencereyi python.exe ile gruplar ve
        görev çubuğunda Python ikonu görünür — oyunun kendi ikonu değil.
        set_mode'dan ÖNCE çağrılmalı.
        """
        if sys.platform!="win32": return
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lagarux.KaranlikTacinLaneti")
        except Exception: pass

    @staticmethod
    def _set_window_icon():
        """Pencere/görev çubuğu ikonu.

        assets/icon64.png paketlenen oyunla birlikte geliyor (kökteki 2048x2048
        icon.png paketlenmiyor ve açılışta yüklemek pahalı). Bulunamazsa
        oyunun kendi piksel sanatından bir ikon üretilir.
        """
        for rel in(("assets","icon64.png"),("assets","icon.ico")):
            path=os.path.join(ASSET_DIR,*rel)
            if not os.path.isfile(path): continue
            try:
                pygame.display.set_icon(pygame.image.load(path).convert_alpha())
                return
            except Exception: pass
        try:
            pygame.display.set_icon(pygame.transform.scale(
                PA.player_surf("down",0,"warrior"),(32,32)))
        except Exception: pass

    def _cycle_language(self,step):
        """Dili sıradakine geçirir ve dile uygun fontları yeniden yükler."""
        cur=Locale.current()
        i=(LANG_CODES.index(cur)+step)%len(LANG_CODES)
        CFG.data["language"]=LANG_CODES[i]
        FontManager.set_language(LANG_CODES[i])
        self.ui=UI()          # fontlar değişti, arayüzü yeniden kur
        UI._bar_cache.clear();UI._panel_cache.clear()
        _TAG_SURF.clear()     # NPC etiketleri yeni dilde yeniden üretilsin

    def _toggle_fullscreen(self):
        CFG.fullscreen = not CFG.fullscreen
        CFG.save()
        flags=pygame.FULLSCREEN if CFG.fullscreen else 0
        self.screen=pygame.display.set_mode((SW,SH),flags)
        SoundManager.play("menu_sel")

    def _reset(self):
        self.maps={
            "ashveil":build_ashveil(),"dark_forest":build_dark_forest(),
            "ruins":build_ruins(),"desert":build_desert(),"ice_cave":build_ice_cave(),
            "shadow_castle":build_shadow_castle(),"village_dungeon":build_village_dungeon(),
            "south_meadow":build_south_meadow(),"west_river":build_west_river(),
            "mystic_library":build_mystic_library(),
            "rocky_pass":build_rocky_pass(),"misty_swamp":build_misty_swamp(),
        }
        for _m in self.maps.values():
            _m.base_chests=set(_m.chests.keys())
            _scatter_props(_m)
        self.cur_key="ashveil";self.cur_map=self.maps["ashveil"]
        self.state="title";self.tick=0;self.frame_no=0
        self.class_sel=0;self.stat_sel=0;self.free_pts=10
        self.temp_stats:Optional[PlayerStats]=None;self.is_lu=False
        self.story_shown=0;self.story_timer=0
        self.flags={
            "ch":1,"speak_aldric":False,"earth_crystal":False,
            "speak_oracle":False,"water_crystal":False,"malachar_defeated":False,
            # Mini görevler
            "sq_scroll1":False,"sq_scroll2":False,"sq_scroll3":False,  # Gizemli Kütüphane
            "sq_fish_done":False,    # Nehir görevi: balıkçıya yardım
            "sq_witch_done":False,   # Bataklık cadısıyla konuş
            "sq_hermit_done":False,  # Münzeviyi ziyaret et
        }
        self.player:Optional[Player]=None
        self.cam_x=0;self.cam_y=0;self.cam_fx=0.0;self.cam_fy=0.0
        self.shake=0;self.shake_mag=0;self.hit_stop=0
        self._acc=0.0;self._last_ms=pygame.time.get_ticks()
        self.dlg_npc=None;self.dlg_lines=[];self.dlg_page=0;self.dlg_reveal=0
        self.hit_fx=[];self.dmg_nums=[]
        self.levelup_timer=0;self.ch_announce=0
        self.trans_alpha=0;self.pending_trans=None;self.transitioning=False;self.entering_name=""
        self.inv_sel=0;self.inv_tab=0;self.eq_sel=0  # eq_sel: ekipman sekmesi imleci
        self.projectiles:List[Projectile]=[]
        self.settings_sel=0  # Ayarlar menüsü seçimi
        self.settings_open=False
        self.pause_open=False
        self._pause_sel=0  # Pause menüsü: 0=devam,1=ayarlar,2=ana menu,3=cikis

    # Oyun dünyasının (HUD, bildirimler) çizildiği durumlar
    HUD_STATES = ("playing","dialog","inventory","quest_log","levelup_alloc")

    # Harita → müzik teması eşleşmesi
    MAP_MUSIC = {
        "ashveil":"village","dark_forest":"forest","ruins":"dungeon",
        "desert":"battle","ice_cave":"dungeon","shadow_castle":"castle",
        "village_dungeon":"dungeon","south_meadow":"village",
        "west_river":"village","mystic_library":"library",
        "rocky_pass":"dungeon","misty_swamp":"forest",
    }

    def _start_game(self):
        st=self.temp_stats;st.hp=st.max_hp;st.mp=st.max_mp
        sx,sy=_snap(self.maps["ashveil"],29,25)
        self.player=Player(sx,sy,st)
        self.cur_key="ashveil";self.cur_map=self.maps["ashveil"];self.state="playing"
        self._cam_snap()
        SoundManager.play_music(self.MAP_MUSIC.get("ashveil","village"))

    CAM_LERP = 0.18   # kamera yumuşatma katsayısı
    CAM_DEAD = 24     # ölü bölge (px): küçük oynamalarda kamera kıpırdamaz

    def _cam_target(self):
        p=self.player
        return (max(0,min(p.px+TILE//2-SW//2, self.cur_map.w*TILE-SW)),
                max(0,min(p.py+TILE//2-SH//2, self.cur_map.h*TILE-SH)))

    def _cam_snap(self):
        """Harita geçişi/başlangıç: kamerayı anında hedefe al."""
        if not self.player: return
        self.cam_fx,self.cam_fy=self._cam_target()
        self.cam_x=int(self.cam_fx);self.cam_y=int(self.cam_fy)

    def _cam(self):
        """Kamerayı hedefe doğru yumuşatarak taşır.

        Oyuncu dururken küçük farklar ölü bölgede yutulur; hareket ederken
        kamera sürekli takip eder. Çizim tam sayı kullanır (cam_x/cam_y).
        """
        if not self.player: return
        tx,ty=self._cam_target()
        dx=tx-self.cam_fx;dy=ty-self.cam_fy
        if self.player.moving or abs(dx)>self.CAM_DEAD or abs(dy)>self.CAM_DEAD:
            self.cam_fx+=dx*self.CAM_LERP
            self.cam_fy+=dy*self.CAM_LERP
        # Çok küçük kalan farkı kapat (sonsuza dek yaklaşmasın)
        if abs(tx-self.cam_fx)<0.5: self.cam_fx=tx
        if abs(ty-self.cam_fy)<0.5: self.cam_fy=ty
        self.cam_x=int(self.cam_fx);self.cam_y=int(self.cam_fy)
        if self.shake>0:
            m=self.shake_mag
            self.cam_x+=random.randint(-m,m);self.cam_y+=random.randint(-m,m)

    def _tile_free(self,tx,ty)->bool:
        if not self.cur_map.walkable(tx,ty): return False
        for n in self.cur_map.npcs:
            if n.tx==tx and n.ty==ty: return False
        for e in self.cur_map.enemies:
            if e.alive and e.tx==tx and e.ty==ty: return False
        return True

    def _try_move(self,dx,dy)->bool:
        """Bir kare adım başlatır. Piksel konumu Entity.advance_step ile yayılır."""
        p=self.player
        if p.moving: return False
        ntx=p.tx+dx;nty=p.ty+dy
        if not self._tile_free(ntx,nty): return False
        # Çapraz adım köşe kesmesin: en az bir komşu kare de açık olmalı
        if dx and dy and not(self.cur_map.walkable(p.tx+dx,p.ty) or self.cur_map.walkable(p.tx,p.ty+dy)):
            return False
        dur=p.stats.move_delay*(1.41 if (dx and dy) else 1.0)
        p.start_step(ntx,nty,dur)
        SoundManager.play("walk")
        pt=(p.tx,p.ty)
        if pt in self.cur_map.transitions:
            dst,tx2,ty2=self.cur_map.transitions[pt];self._start_trans(dst,tx2,ty2)
        return True

    def _start_trans(self,dst,tx,ty):
        self.pending_trans=(dst,tx,ty);self.transitioning=True
        self.trans_alpha=0;self.entering_name=self.maps[dst].name

    def _finish_trans(self):
        dst,tx,ty=self.pending_trans;self.cur_key=dst;self.cur_map=self.maps[dst]
        tx,ty=_snap(self.cur_map,tx,ty)
        self.player.snap(tx,ty)
        self.pending_trans=None;self.transitioning=False;self.trans_alpha=0
        self.projectiles.clear();self._check_ch();self._cam_snap()
        SoundManager.play_music(self.MAP_MUSIC.get(dst,"village"))
        self.save_game()   # otomatik kayıt: harita geçişi doğal bir kontrol noktası

    # ── Kayıt / Yükleme ─────────────────────────────────────────
    # Haritalar her açılışta üreticilerden yeniden kuruluyor; kayıtta yalnızca
    # oyuncunun DEĞİŞTİRDİĞİ şeyler tutulur: açılan sandıklar ve ölen düşmanlar.
    # Böylece kayıt dosyası küçük kalıyor ve harita içeriği güncellenebiliyor.
    def save_game(self)->bool:
        if not self.player: return False
        p=self.player;st=p.stats
        maps={}
        for key,m in self.maps.items():
            taken=[list(c) for c in m.base_chests if c not in m.chests]
            dead=[i for i,e in enumerate(m.enemies) if not e.alive]
            if taken or dead: maps[key]={"chests_taken":taken,"enemies_dead":dead}
        data={
            "version":SAVE_VERSION,"game_version":VERSION,
            "cur_map":self.cur_key,
            "player":{
                "class":st.char_class,"tx":p.tx,"ty":p.ty,"direction":p.direction,
                "str":st.str,"int":st.int_,"agi":st.agi,"vit":st.vit,"wis":st.wis,
                "hp":st.hp,"mp":st.mp,"xp":st.xp,"xp_next":st.xp_next,
                "level":st.level,"gold":st.gold,"skill_points":st.skill_points,
                "inventory":list(p.inventory),"quest_items":list(p.quest_items),
                "equipment":dict(st.equipment),
            },
            "flags":dict(self.flags),
            "maps":maps,
        }
        try:
            tmp=SAVE_FILE+".tmp"
            with open(tmp,"w",encoding="utf-8") as f: json.dump(data,f,indent=1)
            os.replace(tmp,SAVE_FILE)   # yarım yazılmış kayıt kalmasın
            return True
        except Exception:
            return False

    def load_game(self)->bool:
        try:
            with open(SAVE_FILE,encoding="utf-8") as f: data=json.load(f)
            if data.get("version")!=SAVE_VERSION: return False
        except Exception:
            return False
        self._reset()
        try:
            pd=data["player"]
            st=PlayerStats(pd.get("class","warrior"))
            for k,attr in(("str","str"),("int","int_"),("agi","agi"),("vit","vit"),("wis","wis")):
                setattr(st,attr,pd.get(k,getattr(st,attr)))
            st.xp=pd.get("xp",0);st.xp_next=pd.get("xp_next",50)
            st.level=pd.get("level",1);st.gold=pd.get("gold",0)
            st.skill_points=pd.get("skill_points",0)
            st.equipment={k:pd.get("equipment",{}).get(k) for k in EQUIP_SLOTS}
            st.hp=min(pd.get("hp",st.max_hp),st.max_hp)
            st.mp=min(pd.get("mp",st.max_mp),st.max_mp)
            self.player=Player(pd.get("tx",1),pd.get("ty",1),st)
            self.player.direction=pd.get("direction","down")
            self.player.inventory=list(pd.get("inventory",[]))
            self.player.quest_items=list(pd.get("quest_items",[]))
            for k,v in data.get("flags",{}).items():
                # Sabit bayrakların yanında dinamik olanlar da geri yüklenmeli:
                # kill_<tür> sayaçları ve sqpaid_<görev> ödül işaretleri
                # önceden tanımlı değil, süresince oluşuyorlar.
                if k in self.flags or k.startswith(("kill_","sqpaid_")): self.flags[k]=v
            for key,ms in data.get("maps",{}).items():
                m=self.maps.get(key)
                if not m: continue
                for c in ms.get("chests_taken",[]):
                    pos=tuple(c)
                    if pos in m.chests: del m.chests[pos]
                    m.set(pos[0],pos[1],T.FLOOR)
                for i in ms.get("enemies_dead",[]):
                    if 0<=i<len(m.enemies): m.enemies[i].alive=False
            self.cur_key=data.get("cur_map","ashveil")
            self.cur_map=self.maps.get(self.cur_key,self.maps["ashveil"])
            self.state="playing";self._cam_snap()
            SoundManager.play_music(self.MAP_MUSIC.get(self.cur_key,"village"))
            return True
        except Exception:
            self._reset();return False

    def _toast(self,text,col=UI_GN):
        """Ekran ortasında kısa bilgi yazısı (kaydetme gibi işlemler için)."""
        self.dmg_nums.append({"x":SW//2,"y":120,"v":None,"l":90,"col":col,"txt":text,"scr":True})

    def _check_ch(self):
        ch=self.flags["ch"]
        if ch==2 and self.cur_key=="dark_forest": self._advance(3)
        if ch==5 and self.cur_key=="shadow_castle": self._advance(6)

    def _advance(self,ch):
        if self.flags["ch"]<ch: self.flags["ch"]=ch;self.ch_announce=150

    # ── SINIFa ÖZEL AUTO-ATTACK ──────────────────────────────────
    def _auto_attack(self):
        """Space tuşu: sınıfa özel saldırı."""
        p=self.player;st=p.stats
        if p.attacking or st.atk_cd>0: return
        cls=st.char_class
        p.attacking=True;p.atk_frame=0
        st.atk_cd=st.atk_max_cd
        cx=p.px+TILE//2;cy=p.py+TILE//2
        d=p.direction
        ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d,(0,1))

        if cls=="warrior":
            # Koni melee — ön + iki yan tile, yüksek krit
            hit_any=False
            for e in self.cur_map.enemies:
                if not e.alive: continue
                dist=math.hypot(e.tx-p.tx,e.ty-p.ty)
                if dist<=2.0:
                    # Açı kontrolü (45° koni)
                    ex=e.tx-p.tx;ey=e.ty-p.ty
                    if ex==0 and ey==0: continue
                    dot=ox*ex+oy*ey
                    if dot>0 or dist<=1.3:  # Arkaya da kısa mesafede
                        is_crit=random.random()<(st.crit+0.15)
                        self._hit(e,int(st.attack*1.1),is_crit);hit_any=True
            if hit_any: self.ps.emit_magic(cx+ox*TILE,cy+oy*TILE,col=(255,200,80))

        elif cls=="mage":
            # Arcane bolt — en yakın düşmana oto-nişan, yoksa yöne atar
            target=None;min_d=7*TILE
            for e in self.cur_map.enemies:
                if not e.alive: continue
                dist=math.hypot((e.px+TILE//2)-cx,(e.py+TILE//2)-cy)
                if dist<min_d: min_d=dist;target=e
            if target:
                tdx=(target.px+TILE//2)-cx;tdy=(target.py+TILE//2)-cy
                mag=math.hypot(tdx,tdy)
                if mag>0: tdx/=mag;tdy/=mag
                self._proj(cx,cy,tdx,tdy,6,"arcane_bolt",int(st.magic_atk*0.85))
            else:
                self._proj(cx,cy,float(ox),float(oy),6,"arcane_bolt",int(st.magic_atk*0.85))
            self.ps.emit(cx,cy,5,(140,80,255),4.0,15)

        elif cls=="archer":
            # Hassas ok — baktığı yöne, yüksek krit, orta hasar
            dmg=int(st.attack*0.95)
            is_crit=random.random()<(st.crit+0.10)
            if is_crit: dmg=int(dmg*2.0)
            pr=self._proj(cx,cy,float(ox),float(oy),7,"arrow",dmg)
            SoundManager.play("arrow")
            if is_crit and pr:
                self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":50,"col":UI_GD,"txt":T_("ui.crit")})
            self.ps.emit(cx,cy,4,(80,220,80),3.0,15)

        elif cls=="healer":
            # Kutsal melee darbe + küçük iyileşme
            hit_any=False
            for e in self.cur_map.enemies:
                if not e.alive: continue
                if math.hypot(e.tx-p.tx,e.ty-p.ty)<=1.6:
                    self._hit(e,int(st.magic_atk*0.9));hit_any=True
            if hit_any:
                heal_amt=max(2,st.wis)
                st.heal(heal_amt)
                self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":heal_amt,"l":40,"col":HP_G,"txt":None})
            self.ps.emit(cx,cy,6,(255,240,100),3.0,20)

    def _proj(self,x,y,dx,dy,spd,kind,dmg):
        mag=math.hypot(dx,dy)
        if mag>0: dx/=mag;dy/=mag
        pr=Projectile(float(x),float(y),dx,dy,float(spd),dmg,kind,"player")
        self.projectiles.append(pr);return pr

    def add_shake(self,mag,frames):
        """Ekran sarsıntısı — mevcut sarsıntıdan güçlüyse onu ezer."""
        if mag>=self.shake_mag or self.shake<=0:
            self.shake_mag=mag
        self.shake=max(self.shake,frames)

    def _knockback(self,e,frames=5):
        """Düşmanı oyuncudan bir kare uzağa iter (boss'lar sabit durur)."""
        if e.is_boss or not e.alive or e.moving: return
        p=self.player
        dx=e.tx-p.tx;dy=e.ty-p.ty
        if dx==0 and dy==0: return
        if abs(dx)>=abs(dy): dx=1 if dx>0 else -1;dy=0
        else: dy=1 if dy>0 else -1;dx=0
        nx2,ny2=e.tx+dx,e.ty+dy
        if self.cur_map.walkable(nx2,ny2) and not any(
                o.alive and o.tx==nx2 and o.ty==ny2 for o in self.cur_map.enemies if o is not e):
            e.start_step(nx2,ny2,frames)

    def _hit(self,e,dmg,crit=False):
        if crit: dmg=int(dmg*1.8)
        e.hp-=dmg;e.hp=max(0,e.hp)
        col=UI_GD if crit else HP_R
        self.hit_fx.append({"x":e.px+TILE//2,"y":e.py+TILE//2,"f":0,"mf":20})
        self.dmg_nums.append({"x":e.px+TILE//2,"y":e.py,"v":dmg,"l":45,"col":col,"txt":T_("ui.crit") if crit else None})
        self.ps.emit_hit(e.px+TILE//2,e.py+TILE//2)
        SoundManager.play("hit_heavy" if e.is_boss else "hit")
        # Vuruş hissi: kısa donma + krit/boss'ta sarsıntı, kritte geri itme
        self.hit_stop=max(self.hit_stop,5 if crit else 3)
        if crit or e.is_boss: self.add_shake(4 if crit else 2,8)
        if crit: self._knockback(e)
        if e.hp<=0: self._kill(e)

    def _kill(self,e):
        e.alive=False
        for item in e.loot:
            if item=="gold": self.player.stats.gold+=5
            elif item in("earth_c","water_c"):
                self.player.quest_items.append(item);self._quest_item(item)
            else: self.player.inventory.append(item)
        lv=self.player.stats.gain_xp(e.xp_r);self.player.stats.gold+=random.randint(1,4)
        self.ps.emit_xp(e.px+TILE//2,e.py+TILE//2);self.ps.emit_gold(e.px+TILE//2,e.py+TILE//2)
        # Yan görev sayacı: her tür için ayrı
        kk="kill_"+e.kind
        self.flags[kk]=self.flags.get(kk,0)+1
        if lv: self.levelup_timer=180; SoundManager.play("level_up")
        if e.is_boss and e.kind=="malachar": self.flags["malachar_defeated"]=True;self.state="victory";SoundManager.play("victory")

    def _check_side_quests(self):
        """Tamamlanan yan görevin ödülünü bir kez verir."""
        for sq in SIDE_QUESTS:
            paid="sqpaid_"+sq["id"]
            if self.flags.get(paid) or not sq_done(sq,self.flags): continue
            self.flags[paid]=True
            self.player.stats.gold+=sq["gold"]
            self.player.stats.gain_xp(sq["xp"])
            SoundManager.play("chest")
            self._toast("%s — %s  (+%d %s, +%d XP)"%(
                T_("ui.sq_done"),T_(sq["title"]),sq["gold"],T_("gold"),sq["xp"]),UI_GD)

    def _quest_item(self,item):
        if item=="earth_c" and not self.flags["earth_crystal"]:
            self.flags["earth_crystal"]=True;self._advance(4)
            self.dmg_nums.append({"x":SW//2,"y":SH//2-60,"v":None,"l":130,"col":UI_GN,"txt":"Toprak Kristali!","scr":True})
        elif item=="water_c" and not self.flags["water_crystal"]:
            self.flags["water_crystal"]=True;self._advance(6)
            self.dmg_nums.append({"x":SW//2,"y":SH//2-60,"v":None,"l":130,"col":UI_CY,"txt":"Su Kristali!","scr":True})

    # ── Yetenek ─────────────────────────────────────────────────
    def _use_ability(self,slot):
        p=self.player;st=p.stats
        if not st.can_use(slot): SoundManager.play("error");return
        ab=ABILITIES[st.char_class][slot];st.mp-=ab["mp"];st.ab_cds[slot]=ab["cd"]
        SoundManager.play("spell")
        cx=p.px+TILE//2;cy=p.py+TILE//2
        d=p.direction;ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d,(0,1))
        aid=ab["id"]
        if aid=="shield_bash":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=1.8:
                    self._hit(e,int(st.attack*1.5))
                    nx2=e.tx+ox;ny2=e.ty+oy
                    if self.cur_map.walkable(nx2,ny2): e.start_step(nx2,ny2,5)
            self.ps.emit_magic(cx,cy,col=(220,120,60))
        elif aid=="whirlwind":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=2.2: self._hit(e,int(st.attack*1.2))
            self.ps.emit(cx,cy,30,(200,150,60),6.0,40)
        elif aid=="war_cry":
            st.buffs["war_cry"]=180;self.ps.emit(cx,cy,25,(220,80,40),5.0,50)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":80,"col":(220,80,40),"txt":T_("ui.shout_war_cry")})
        elif aid=="earthquake":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.attack*2.0))
            for _ in range(40): self.ps.emit(cx+random.randint(-96,96),cy+random.randint(-96,96),5,(180,120,40),3.0,30)
        elif aid=="freeze":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.0:
                    e.frozen=max(e.frozen,120);self._hit(e,int(st.magic_atk*0.8))
            SoundManager.play("freeze")
            self.ps.emit(cx,cy,25,(80,180,255),5.0,50)
        elif aid=="meteor":
            for _ in range(5):
                mx=p.tx+random.randint(-3,3);my=p.ty+random.randint(-3,3)
                for e in self.cur_map.enemies:
                    if e.alive and abs(e.tx-mx)<=1 and abs(e.ty-my)<=1: self._hit(e,int(st.magic_atk*1.8))
                self.ps.emit(mx*TILE+TILE//2,my*TILE+TILE//2,15,(255,80,20),6.0,35)
        elif aid=="arcane_nova":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=4.0: self._hit(e,int(st.magic_atk*2.2))
            for ang in range(0,360,20):
                dx2=math.cos(math.radians(ang));dy2=math.sin(math.radians(ang))
                self._proj(cx,cy,dx2,dy2,4,"shadow_bolt",int(st.magic_atk*0.6))
        elif aid=="time_stop":
            for e in self.cur_map.enemies: e.frozen=max(e.frozen,240)
            self.ps.emit(cx,cy,40,(180,180,255),6.0,60)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":100,"col":(180,180,255),"txt":T_("ui.shout_time")})
        elif aid=="multi_shot":
            for ang in[-25,0,25]:
                rad=math.atan2(oy,ox)+math.radians(ang);self._proj(cx,cy,math.cos(rad),math.sin(rad),6,"arrow",int(st.attack*0.9))
        elif aid=="trap":
            t=Trap(p.tx+ox,p.ty+oy,int(st.attack*1.8));self.cur_map.traps.append(t)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":60,"col":(180,140,60),"txt":T_("ui.trap_set")})
        elif aid=="rain_arrows":
            for ang_d in range(0,360,45):
                rad=math.radians(ang_d);self._proj(cx,cy,math.cos(rad),math.sin(rad),5,"arrow",int(st.attack*0.8))
        elif aid=="shadow_step":
            for e in self.cur_map.enemies:
                if not e.alive: continue
                nx2=e.tx-ox;ny2=e.ty-oy
                if self.cur_map.walkable(nx2,ny2):
                    p.snap(nx2,ny2);self._hit(e,int(st.attack*2.0))
                    self.ps.emit(cx,cy,20,(60,40,120),5.0,30);break
        elif aid=="mass_heal":
            amt=int(25+st.wis*2);st.heal(amt)
            self.ps.emit_magic(cx,cy,col=(80,220,120))
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":amt,"l":60,"col":HP_G,"txt":None})
        elif aid=="holy_shield":
            st.buffs["holy_shield"]=120;self.ps.emit_magic(cx,cy,col=(255,220,80))
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":60,"col":(255,220,60),"txt":T_("ui.shout_shield")})
        elif aid=="divine_storm":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.magic_atk*1.8))
            for _ in range(30): self.ps.emit(cx+random.randint(-80,80),cy+random.randint(-80,80),6,(255,240,120),4.0,40)
        elif aid=="resurrection":
            st.heal(st.max_hp//2);st.restore_mp(st.max_mp//2)
            self.ps.emit(cx,cy,50,(255,200,100),6.0,70)
            self.dmg_nums.append({"x":cx,"y":cy-TILE*2,"v":None,"l":120,"col":(255,180,80),"txt":T_("ui.shout_resurrect")})

    def _update_projs(self):
        alive=[]
        for pr in self.projectiles:
            if not pr.alive: continue
            pr.x+=pr.dx*pr.speed;pr.y+=pr.dy*pr.speed;pr.frame+=1
            tx=int(pr.x//TILE);ty=int(pr.y//TILE)
            if not(0<=tx<self.cur_map.w and 0<=ty<self.cur_map.h): continue
            if not self.cur_map.walkable(tx,ty): continue
            if pr.frame>140: continue
            hit=False
            for e in self.cur_map.enemies:
                if not e.alive: continue
                er=pygame.Rect(e.px+2,e.py+2,TILE-4,TILE-4)
                if er.collidepoint(pr.x,pr.y):
                    self._hit(e,pr.dmg,random.random()<0.08)
                    if pr.kind=="ice_bolt": e.frozen=max(e.frozen,100)
                    if not pr.pierce: hit=True;break
            if hit: continue
            alive.append(pr)
        self.projectiles=alive

    def _update_traps(self):
        for tt in self.cur_map.traps:
            if not tt.active: continue
            if tt.triggered:
                tt.timer+=1
                if tt.timer>20: tt.active=False
                continue
            for e in self.cur_map.enemies:
                if e.alive and abs(e.tx-tt.tx)<=1 and abs(e.ty-tt.ty)<=1:
                    self._hit(e,tt.dmg);tt.triggered=True;tt.timer=0
                    SoundManager.play("trap")
                    self.ps.emit(tt.tx*TILE+TILE//2,tt.ty*TILE+TILE//2,20,(255,180,40),5.0,35);break
        self.cur_map.traps=[tt for tt in self.cur_map.traps if tt.active]

    NPC_WANDER_R = 2   # NPC evinden en fazla bu kadar uzaklaşır

    def _update_npcs(self):
        """NPC'ler arada bir kendi çevrelerinde adım atar — köy canlı görünsün."""
        p=self.player
        for n in self.cur_map.npcs:
            n.advance_step()
            if n.moving: continue
            if n.idle_cd>0: n.idle_cd-=1;continue
            n.idle_cd=random.randint(120,420)
            dx,dy=random.choice(((1,0),(-1,0),(0,1),(0,-1)))
            nx2,ny2=n.tx+dx,n.ty+dy
            if abs(nx2-n.home_tx)>self.NPC_WANDER_R or abs(ny2-n.home_ty)>self.NPC_WANDER_R: continue
            if not self.cur_map.walkable(nx2,ny2): continue
            if (nx2,ny2)==(p.tx,p.ty): continue
            if any(o is not n and o.tx==nx2 and o.ty==ny2 for o in self.cur_map.npcs): continue
            if any(e.alive and e.tx==nx2 and e.ty==ny2 for e in self.cur_map.enemies): continue
            if (nx2,ny2) in self.cur_map.chests: continue
            n.direction=("right" if dx>0 else "left") if dx else("down" if dy>0 else "up")
            n.start_step(nx2,ny2,26)

    def _bfs_step(self,e,gx,gy,radius=8):
        """Düşmandan oyuncuya kısa menzilli BFS; atılacak ilk kareyi döndürür.

        Eksen-açgözlü takip duvar köşelerinde takılıyordu. Yarıçap sınırlı
        olduğu için maliyeti küçük (en fazla ~17x17 düğüm) ve yalnızca
        kovalayan düşman adım atacakken çalışır.
        """
        m=self.cur_map;start=(e.tx,e.ty);goal=(gx,gy)
        if start==goal: return None
        occupied={(o.tx,o.ty) for o in m.enemies if o.alive and o is not e}
        prev={start:None};q=deque([start])
        found=False
        while q:
            cur=q.popleft()
            if cur==goal: found=True;break
            cx,cy=cur
            for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                nxt=(cx+dx,cy+dy)
                if nxt in prev: continue
                if abs(nxt[0]-e.tx)>radius or abs(nxt[1]-e.ty)>radius: continue
                if nxt!=goal and(not m.walkable(*nxt) or nxt in occupied): continue
                prev[nxt]=cur;q.append(nxt)
        if not found: return None
        node=goal
        while prev[node] is not None and prev[node]!=start: node=prev[node]
        return None if node==goal else node   # bitişikse adım yok, saldırı sırası

    def _update_enemies(self):
        p=self.player;ppx=p.px+TILE//2;ppy=p.py+TILE//2
        for e in self.cur_map.enemies:
            if not e.alive: continue
            e.advance_step()   # başlamış adımı tamamla (donsa bile kareye otursun)
            if e.frozen>0: e.frozen-=1;continue
            ex=e.px+TILE//2;ey=e.py+TILE//2;dist=math.hypot(ex-ppx,ey-ppy)
            if dist<e.agro_range: e.state="chase"
            elif e.state=="chase" and dist>e.agro_range*1.5: e.state="idle"
            if e.state!="chase":
                e.wind_up=0;continue
            adjacent=abs(e.tx-p.tx)<=1 and abs(e.ty-p.ty)<=1
            if e.atk_cd>0: e.atk_cd-=1

            # ── Saldırı telegrafı: önce hazırlanır, sonra vurur ──
            if e.wind_up>0:
                e.wind_up-=1
                if e.wind_up==0:
                    if adjacent: self._enemy_strike(e,p,ppx,ppy)
                    e.atk_cd=self.ENEMY_ATK_CD
                continue   # hazırlanırken yerinden kıpırdamaz
            if adjacent:
                if e.atk_cd<=0:
                    e.wind_up=self.ENEMY_WINDUP
                    if e.is_boss: SoundManager.play("boss_alert")
                continue

            e.move_cd-=1
            spd=max(6,20-p.stats.level*2)
            if e.kind in("wolf","ice_wolf"): spd=max(4,spd-4)
            if e.kind=="golem": spd+=8
            if e.move_cd<=0:
                e.move_cd=spd
                step=self._bfs_step(e,p.tx,p.ty)
                if step is None:
                    # Yol bulunamadı (uzak/kapalı) → eski basit takibe düş
                    ddx=0 if e.tx==p.tx else(1 if p.tx>e.tx else -1)
                    ddy=0 if e.ty==p.ty else(1 if p.ty>e.ty else -1)
                    if abs(p.tx-e.tx)>=abs(p.ty-e.ty): ddy=0
                    else: ddx=0
                    step=(e.tx+ddx,e.ty+ddy)
                nx2,ny2=step
                if(self.cur_map.walkable(nx2,ny2) and
                   not any(o.alive and o.tx==nx2 and o.ty==ny2 for o in self.cur_map.enemies if o is not e) and
                   not(nx2==p.tx and ny2==p.ty)):
                    e.start_step(nx2,ny2,spd)

    ENEMY_WINDUP = 26   # saldırı öncesi hazırlanma (kaçmak için pencere)
    ENEMY_ATK_CD = 14   # iki saldırı arası bekleme
    # 26+14=40 kare: telegraf oncesi ritmin aynisi, ustune kacma penceresi.

    def _enemy_strike(self,e,p,ppx,ppy):
        """Telegraf tamamlandı: hasar uygula."""
        if p.invincible>0: return
        dmg=max(1,e.atk-p.stats.defense+random.randint(-2,3))
        if "holy_shield" in p.stats.buffs:
            sh=p.stats.buffs["holy_shield"]
            if isinstance(sh,int): p.stats.buffs["holy_shield"]=max(0,sh-dmg);dmg=0
        p.stats.hp-=dmg;p.stats.hp=max(0,p.stats.hp);p.invincible=40
        self.ps.emit_hit(ppx,ppy)
        self.dmg_nums.append({"x":ppx,"y":ppy-TILE//2,"v":dmg,"l":40,"col":HP_R})
        if dmg>0: self.add_shake(5 if e.is_boss else 3,10)
        if p.stats.hp<=0: self.state="gameover";SoundManager.play("death")

    DLG_SPEED = 2   # daktilo: kare başına harf

    def _dlg_page_len(self)->int:
        lpp=4;pl=[dlg_line(e) for e in self.dlg_lines[self.dlg_page*lpp:(self.dlg_page+1)*lpp]]
        return sum(len(l) for l in pl)

    def _interact_target(self):
        """Etkileşilebilecek hedefi bulur: ('npc', nesne) veya ('chest', (tx,ty)).

        Önce bakılan kare denenir; orada bir şey yoksa komşu karelerde **tek**
        bir aday varsa o kabul edilir (bir karelik tolerans — hizalama derdi
        oyuncuyu uğraştırmasın).
        """
        p=self.player
        ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(p.direction,(0,1))
        def at(tx,ty):
            for npc in self.cur_map.npcs:
                if npc.tx==tx and npc.ty==ty: return("npc",npc)
            if(tx,ty) in self.cur_map.chests: return("chest",(tx,ty))
            return None
        front=at(p.tx+ox,p.ty+oy)
        if front: return front
        near=[t for t in(at(p.tx+dx,p.ty+dy) for dx,dy in((1,0),(-1,0),(0,1),(0,-1))) if t]
        return near[0] if len(near)==1 else None

    def _interact(self):
        p=self.player
        target=self._interact_target()
        if not target: return
        kind,obj=target
        itx,ity=(obj.tx,obj.ty) if kind=="npc" else obj
        for npc in self.cur_map.npcs:
            if npc.tx==itx and npc.ty==ity:
                lines=npc.get_dialog(self.flags);self.dlg_npc=npc;self.dlg_lines=lines
                self.dlg_page=0;self.dlg_reveal=0;self.state="dialog"
                if npc.name=="npc.yasli_aldric" and not self.flags["speak_aldric"]:
                    self.flags["speak_aldric"]=True;self._advance(2)
                elif npc.name=="npc.oracle_nyx" and not self.flags.get("speak_oracle") and self.flags.get("earth_crystal"):
                    self.flags["speak_oracle"]=True;self._advance(5)
                elif npc.name=="npc.bataklik_cadisi": self.flags["sq_witch_done"]=True
                elif npc.name=="npc.munzevi": self.flags["sq_hermit_done"]=True
                elif npc.name=="npc.balikci_riva" and not self.flags.get("sq_fish_done"):
                    self.flags["sq_fish_done"]=True;SoundManager.play("chest")
                    self.dmg_nums.append({"x":npc.tx*TILE,"y":npc.ty*TILE-TILE,"v":None,"l":100,"col":UI_CY,"txt":T_("ui.sq_done")})
                return
        if(itx,ity) in self.cur_map.chests:
            loot=self.cur_map.chests.pop((itx,ity))
            for ik in loot:
                if ik=="gold": p.stats.gold+=ITEMS["gold"][3]
                elif ik in("earth_c","water_c"): p.quest_items.append(ik);self._quest_item(ik)
                elif ik in("scroll1","scroll2","scroll3"):
                    p.inventory.append(ik)
                    flag_k="sq_"+ik
                    if not self.flags.get(flag_k):
                        self.flags[flag_k]=True;SoundManager.play("spell")
                        self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py-TILE,"v":None,"l":100,"col":UI_PR,"txt":fT_("ui.scroll_found")})
                else: p.inventory.append(ik)
            self.cur_map.set(itx,ity,T.FLOOR);self.ps.emit_gold(itx*TILE+TILE//2,ity*TILE+TILE//2);SoundManager.play("chest")
            self.dmg_nums.append({"x":itx*TILE+TILE//2,"y":ity*TILE,"v":None,"l":70,"col":UI_GD,"txt":T_("chest_opened")})

    def _inv_use_item(self):
        """Envanterde seçili eşyayı kullan / ekipmanı giy."""
        p=self.player;u=list(dict.fromkeys(p.inventory))
        if not(0<=self.inv_sel<len(u)): return
        ik=u[self.inv_sel];itm=ALL_ITEMS.get(ik)
        if not itm: return
        typ=itm[2]
        if typ=="heal": p.stats.heal(itm[3]);p.inventory.remove(ik);self.ps.emit_magic(p.px+TILE//2,p.py);SoundManager.play("heal")
        elif typ=="mana": p.stats.restore_mp(itm[3]);p.inventory.remove(ik)
        elif typ=="quest_sq":
            self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py-TILE,"v":None,"l":60,"col":UI_PR,"txt":T_("ui.take_librarian")})
        elif typ.startswith("stat_"): p.stats.apply_item(typ,itm[3]);p.inventory.remove(ik)
        elif typ=="equip":
            old=p.stats.equip(ik)
            SoundManager.play("equip")
            if old=="":  # başarılı ekipleme, eski slot boştu
                p.inventory.remove(ik)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":fT_("ui.equipped_msg")})
            elif old and old!=ik:  # eski ekipman çıkarıldı, envantera döndü
                p.inventory.remove(ik);p.inventory.append(old)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":fT_("ui.swapped_msg")})
            elif old==ik:  # zaten ekipli, çıkar
                slot=EQUIP_ITEMS[ik][3];p.stats.unequip(slot)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_RD,"txt":fT_("ui.removed_msg")})

    # ── Ana Döngü ────────────────────────────────────────────────
    # ── Güncelleme ───────────────────────────────────────────────
    STEP_MS = 1000.0/FPS   # bir mantık adımının süresi
    MAX_STEPS = 5          # kare çok gecikirse en fazla bu kadar adım telafi et

    def _read_move_input(self):
        """Basılı yön tuşlarından (çapraz dahil) birim vektör üretir."""
        keys=pygame.key.get_pressed()
        dx=(1 if(keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0)-(1 if(keys[pygame.K_LEFT] or keys[pygame.K_a]) else 0)
        dy=(1 if(keys[pygame.K_DOWN] or keys[pygame.K_s]) else 0)-(1 if(keys[pygame.K_UP] or keys[pygame.K_w]) else 0)
        return dx,dy

    def _move_player(self):
        p=self.player
        dx,dy=self._read_move_input()
        if dx or dy:
            # Bakış yönü: çaprazda yatay eksen okunur kalıyor
            p.direction=("right" if dx>0 else "left") if dx else("down" if dy>0 else "up")
        if p.moving or self.transitioning or not(dx or dy): return
        # Önce çapraz, olmazsa tek eksene kay (duvara sürtünerek ilerleme)
        if dx and dy:
            if self._try_move(dx,dy): return
            if self._try_move(dx,0): return
            self._try_move(0,dy)
        else:
            self._try_move(dx,dy)

    def _update(self):
        """Bir mantık adımı. Tüm sayaçlar kare cinsinden olduğu için sabit adımlı."""
        self.frame_no+=1
        if self.shake>0:
            self.shake-=1
            if self.shake==0: self.shake_mag=0
        if self.state=="story":
            self.story_timer+=1
            if self.story_timer%35==0: self.story_shown=min(self.story_shown+1,len(STORY_LINES))

        # Vuruş anında kısa donma: darbenin ağırlığını hissettirir.
        if self.hit_stop>0:
            self.hit_stop-=1
            if self.player: self._cam()
            return

        if self.state=="dialog":
            self.dlg_reveal=min(self._dlg_page_len(),self.dlg_reveal+self.DLG_SPEED)
        if self.state=="playing" and self.player and not self.pause_open:
            p=self.player
            self._move_player()
            p.advance_step()
            if p.moving: p.frame+=1
            if p.invincible>0: p.invincible-=1
            if p.attacking: p.atk_frame+=1
            if p.atk_frame>=p.atk_max: p.attacking=False
            p.stats.tick_cds();p.stats.tick_buffs()
            # NOT: self.tick milisaniyedir; periyodik iş için kare sayacı kullanılır.
            if p.stats.char_class=="healer" and self.frame_no%120==0:
                if p.stats.hp<p.stats.max_hp and p.stats.mp>=3: p.stats.heal(2);p.stats.mp-=3
            if self.levelup_timer>0: self.levelup_timer-=1
            if self.ch_announce>0: self.ch_announce-=1
            self._update_npcs();self._update_enemies();self._update_projs();self._update_traps()
            self._check_side_quests()
            if self.levelup_timer==100 and p.stats.skill_points>0:
                self.stat_sel=0;self.temp_stats=p.stats;self.is_lu=True;self.state="levelup_alloc"
        elif self.player:
            # Menü/diyalog açıkken bile başlamış adım tamamlansın (yarım karede kalmasın)
            self.player.advance_step()

        if self.transitioning and self.pending_trans:
            self.trans_alpha=min(255,self.trans_alpha+10)
            if self.trans_alpha>=255: self._finish_trans()
        elif self.trans_alpha>0: self.trans_alpha=max(0,self.trans_alpha-10)

        self.ps.update();self._cam()

    def _step_updates(self):
        """Gerçek geçen süreye göre sabit adım çalıştırır.

        Tüm oyun mantığı kare sayan sayaçlarla yazıldığı için her sayacı dt ile
        çarpmak yerine mantığı sabit 1/60 adımda tutuyoruz: FPS düşse de oyun
        yavaşlamaz, sayaçların anlamı da bozulmaz.
        """
        now=self.tick
        self._acc=min(self._acc+(now-self._last_ms), self.STEP_MS*self.MAX_STEPS)
        self._last_ms=now
        steps=0
        while self._acc>=self.STEP_MS and steps<self.MAX_STEPS:
            self._update();self._acc-=self.STEP_MS;steps+=1

    def run(self):
        running=True
        self._last_ms=pygame.time.get_ticks();self._acc=0.0
        while running:
            self.tick=pygame.time.get_ticks(); self.clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT:
                    running=False; break

                if ev.type==pygame.KEYDOWN:
                    k=ev.key

                    # ── Evrensel kısayollar (her state'te çalışır) ──
                    if k==pygame.K_F11:
                        self._toggle_fullscreen(); continue

                    # ── Settings overlay açıkken ──
                    if self.settings_open:
                        opts_s=["fullscreen","master_vol","sfx_vol","music_vol","language","show_fps"]
                        if k==pygame.K_ESCAPE or k==pygame.K_F1:
                            self.settings_open=False; CFG.save(); SoundManager.play("menu_back")
                        elif k in(pygame.K_UP,pygame.K_w):
                            self.settings_sel=max(0,self.settings_sel-1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_DOWN,pygame.K_s):
                            self.settings_sel=min(len(opts_s)-1,self.settings_sel+1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RIGHT,pygame.K_d,pygame.K_RETURN):
                            key2=opts_s[self.settings_sel]
                            if key2=="fullscreen": self._toggle_fullscreen()
                            elif key2=="master_vol": CFG.data["master_vol"]=min(100,CFG.data.get("master_vol",80)+10); SoundManager.update_music_volume()
                            elif key2=="sfx_vol":   CFG.data["sfx_vol"]=min(100,CFG.data.get("sfx_vol",80)+10)
                            elif key2=="music_vol": CFG.data["music_vol"]=min(100,CFG.data.get("music_vol",60)+10); SoundManager.update_music_volume()
                            elif key2=="language":  self._cycle_language(+1)
                            elif key2=="show_fps":  CFG.data["show_fps"]=not CFG.data.get("show_fps",False)
                            CFG.save(); SoundManager.play("menu_sel")
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            key2=opts_s[self.settings_sel]
                            if key2=="language": self._cycle_language(-1)
                            elif key2=="master_vol": CFG.data["master_vol"]=max(0,CFG.data.get("master_vol",80)-10); SoundManager.update_music_volume()
                            elif key2=="sfx_vol":  CFG.data["sfx_vol"]=max(0,CFG.data.get("sfx_vol",80)-10)
                            elif key2=="music_vol":CFG.data["music_vol"]=max(0,CFG.data.get("music_vol",60)-10); SoundManager.update_music_volume()
                            CFG.save(); SoundManager.play("menu_sel")
                        continue  # Settings açıkken başka input geçmesin

                    # ── Pause menüsü açıkken ──
                    if self.pause_open:
                        if k in(pygame.K_UP,pygame.K_w):
                            self._pause_sel=max(0,self._pause_sel-1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_DOWN,pygame.K_s):
                            self._pause_sel=min(len(UI.PAUSE_OPTS)-1,self._pause_sel+1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RETURN,pygame.K_e,pygame.K_SPACE):
                            if self._pause_sel==0:   # Devam
                                self.pause_open=False; SoundManager.play("menu_back")
                            elif self._pause_sel==1: # Kaydet
                                ok=self.save_game()
                                self._toast(T_("ui.saved") if ok else T_("ui.save_failed"),UI_GN if ok else UI_RD)
                                SoundManager.play("chest" if ok else "error")
                                self.pause_open=False
                            elif self._pause_sel==2: # Ayarlar
                                self.settings_open=True; self.settings_sel=0; SoundManager.play("open_ui")
                            elif self._pause_sel==3: # Ana Menü
                                self._reset(); SoundManager.play("menu_back")
                            elif self._pause_sel==4: # Çıkış
                                running=False
                        elif k==pygame.K_ESCAPE:
                            self.pause_open=False; SoundManager.play("menu_back")
                        continue

                    # ── State'e göre input ──
                    if self.state=="title":
                        if k in(pygame.K_RETURN,pygame.K_e):
                            self.state="story"; SoundManager.play("menu_sel")
                        elif k==pygame.K_c and has_save():
                            if self.load_game(): SoundManager.play("menu_sel")
                            else: SoundManager.play("error")
                        elif k==pygame.K_F1:
                            self.settings_open=True; self.settings_sel=0; SoundManager.play("open_ui")

                    elif self.state=="story":
                        if k==pygame.K_RETURN:
                            if self.story_shown<len(STORY_LINES): self.story_shown=len(STORY_LINES)
                            else: self.state="class_select"; SoundManager.play("menu_sel")
                        elif k==pygame.K_SPACE:
                            self.story_shown=min(self.story_shown+1,len(STORY_LINES))
                        elif k==pygame.K_ESCAPE:
                            self.state="title"

                    elif self.state=="class_select":
                        ks=list(CLASS_INFO.keys())
                        if k in(pygame.K_LEFT,pygame.K_a): self.class_sel=max(0,self.class_sel-1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RIGHT,pygame.K_d): self.class_sel=min(len(ks)-1,self.class_sel+1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RETURN,pygame.K_e):
                            self.temp_stats=PlayerStats(ks[self.class_sel]); self.free_pts=10; self.stat_sel=0; self.is_lu=False; self.state="stat_alloc"; SoundManager.play("menu_sel")
                        elif k==pygame.K_ESCAPE:
                            self.state="story"

                    elif self.state=="stat_alloc":
                        st=self.temp_stats; sk_m=["str","int","agi","vit","wis"]; sk=sk_m[self.stat_sel]; rsk="int_" if sk=="int" else sk
                        if k in(pygame.K_UP,pygame.K_w): self.stat_sel=max(0,self.stat_sel-1)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.stat_sel=min(4,self.stat_sel+1)
                        elif k in(pygame.K_RIGHT,pygame.K_d):
                            if self.free_pts>0: setattr(st,rsk,getattr(st,rsk)+1); self.free_pts-=1; SoundManager.play("menu_sel")
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            if getattr(st,rsk)>2: setattr(st,rsk,getattr(st,rsk)-1); self.free_pts+=1; SoundManager.play("menu_sel")
                        elif k==pygame.K_RETURN:
                            if self.is_lu: self.player.stats.skill_points=0; self.state="playing"
                            else: self._start_game()
                        elif k==pygame.K_ESCAPE:
                            self.state="class_select"

                    elif self.state=="dialog":
                        if k in(pygame.K_e,pygame.K_RETURN,pygame.K_SPACE):
                            if self.dlg_reveal<self._dlg_page_len():
                                self.dlg_reveal=self._dlg_page_len()   # once yaziyi tamamla
                            else:
                                self.dlg_page+=1;self.dlg_reveal=0
                                if self.dlg_page*4>=len(self.dlg_lines): self.state="playing"
                        elif k==pygame.K_ESCAPE:
                            self.state="playing"

                    elif self.state=="inventory":
                        u=list(dict.fromkeys(self.player.inventory))
                        if k==pygame.K_TAB: self.inv_tab=1-self.inv_tab; SoundManager.play("menu_sel")
                        elif self.inv_tab==1:
                            # Ekipman sekmesi: kendi imleci (silah / zirh / yuzuk)
                            if k in(pygame.K_UP,pygame.K_w): self.eq_sel=max(0,self.eq_sel-1); SoundManager.play("menu_sel")
                            elif k in(pygame.K_DOWN,pygame.K_s): self.eq_sel=min(2,self.eq_sel+1); SoundManager.play("menu_sel")
                            elif k==pygame.K_e:
                                slot=EQUIP_SLOTS[self.eq_sel]
                                old=self.player.stats.unequip(slot)
                                if old:
                                    self.player.inventory.append(old); SoundManager.play("equip")
                                else:
                                    SoundManager.play("error")
                            elif k in(pygame.K_i,pygame.K_ESCAPE): self.state="playing"
                        elif k in(pygame.K_LEFT,pygame.K_a): self.inv_sel=max(0,self.inv_sel-1)
                        elif k in(pygame.K_RIGHT,pygame.K_d): self.inv_sel=min(max(0,len(u)-1),self.inv_sel+1)
                        elif k in(pygame.K_UP,pygame.K_w): self.inv_sel=max(0,self.inv_sel-5)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.inv_sel=min(max(0,len(u)-1),self.inv_sel+5)
                        elif k==pygame.K_e: self._inv_use_item()
                        elif k in(pygame.K_i,pygame.K_ESCAPE): self.state="playing"

                    elif self.state=="quest_log":
                        if k in(pygame.K_q,pygame.K_ESCAPE): self.state="playing"

                    elif self.state=="levelup_alloc":
                        st=self.player.stats; sk_m=["str","int","agi","vit","wis"]; sk=sk_m[self.stat_sel]; rsk="int_" if sk=="int" else sk; fp=st.skill_points
                        if k in(pygame.K_UP,pygame.K_w): self.stat_sel=max(0,self.stat_sel-1)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.stat_sel=min(4,self.stat_sel+1)
                        elif k in(pygame.K_RIGHT,pygame.K_d):
                            if fp>0: setattr(st,rsk,min(30,getattr(st,rsk)+1)); st.skill_points-=1; SoundManager.play("menu_sel")
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            if getattr(st,rsk)>2: setattr(st,rsk,getattr(st,rsk)-1); st.skill_points+=1
                        elif k==pygame.K_RETURN:
                            if st.skill_points==0: self.state="playing"

                    elif self.state=="gameover":
                        if k==pygame.K_r: self._reset()

                    elif self.state=="victory":
                        if k in(pygame.K_ESCAPE,pygame.K_RETURN): self._reset()

                    elif self.state=="playing":
                        if k==pygame.K_ESCAPE:
                            self.pause_open=True; self._pause_sel=0; SoundManager.play("open_ui")
                        elif k==pygame.K_F1:
                            self.settings_open=True; self.settings_sel=0; SoundManager.play("open_ui")
                        elif k==pygame.K_i:
                            self.inv_sel=0; self.inv_tab=0; self.state="inventory"; SoundManager.play("open_ui")
                        elif k==pygame.K_q: self.state="quest_log"; SoundManager.play("open_ui")
                        elif k==pygame.K_e: self._interact()
                        elif k==pygame.K_SPACE: self._auto_attack()
                        elif k in(pygame.K_1,pygame.K_KP1): self._use_ability(0)
                        elif k in(pygame.K_2,pygame.K_KP2): self._use_ability(1)
                        elif k in(pygame.K_3,pygame.K_KP3): self._use_ability(2)
                        elif k in(pygame.K_4,pygame.K_KP4): self._use_ability(3)
                        elif k==pygame.K_u:
                            if self.player and self.player.stats.skill_points>0:
                                self.stat_sel=0; self.temp_stats=self.player.stats; self.is_lu=True; self.state="levelup_alloc"
            self._step_updates()

            # ─── Çizim ───────────────────────────────────────────
            self.screen.fill(DKG)
            if self.state=="title": self.ui.draw_title(self.screen,self.tick)
            elif self.state=="story": self.ui.draw_story(self.screen,self.story_shown,self.tick)
            elif self.state=="class_select": self.ui.draw_class_select(self.screen,self.class_sel,self.tick)
            elif self.state=="stat_alloc": self.ui.draw_stat_alloc(self.screen,self.temp_stats,self.free_pts,self.stat_sel,False,self.tick)
            else:
                if self.cur_map:
                    self.cur_map.light_at=((self.player.px-self.cam_x+TILE//2,
                                            self.player.py-self.cam_y+TILE//2)
                                           if self.player else None)
                    self.cur_map.draw(self.screen,self.cam_x,self.cam_y,self.tick)
                if self.player:
                    p=self.player;p.draw(self.screen,self.cam_x,self.cam_y)
                    # Saldırı efekti
                    if p.attacking:
                        t2=p.atk_frame/p.atk_max;d3=p.direction
                        ox3,oy3={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d3,(0,1))
                        sx3=p.px+TILE//2+ox3*TILE-self.cam_x;sy3=p.py+TILE//2+oy3*TILE-self.cam_y
                        rr3=int(20*math.sin(t2*math.pi));aa3=int(200*(1-t2))
                        if rr3>0:
                            ats=pygame.Surface((rr3*2+4,rr3*2+4),pygame.SRCALPHA)
                            ac={"warrior":(255,200,80),"mage":(140,80,255),"archer":(80,255,120),"healer":(255,240,100)}.get(p.stats.char_class,(255,200,80))
                            pygame.draw.circle(ats,(*ac,aa3),(rr3+2,rr3+2),max(2,rr3));self.screen.blit(ats,(sx3-rr3-2,sy3-rr3-2))
                    # Mermiler
                    for pr in self.projectiles:
                        sp=PA.proj_surf(pr.kind,pr.frame)
                        ang=math.degrees(math.atan2(pr.dy,pr.dx));sp_r=pygame.transform.rotate(sp,-ang)
                        self.screen.blit(sp_r,(int(pr.x-sp_r.get_width()//2-self.cam_x),int(pr.y-sp_r.get_height()//2-self.cam_y)))
                    # Hit fx
                    self.hit_fx=[h for h in self.hit_fx if h["f"]<h["mf"]]
                    for h in self.hit_fx:
                        hs=PA.hit_fx_surf(h["f"],h["mf"]);self.screen.blit(hs,(h["x"]-24-self.cam_x,h["y"]-24-self.cam_y));h["f"]+=1
                    # Hasar/bilgi sayıları
                    alive_d=[]
                    for dn in self.dmg_nums:
                        dn["l"]-=1
                        if dn["l"]<=0: continue
                        aa4=min(255,int(dn["l"]*5.5));dy4=(45-max(0,dn["l"]))*0.45
                        txt4=dn.get("txt") or(f"-{dn['v']}" if dn.get("v") else "")
                        if not txt4: alive_d.append(dn);continue
                        ts4=self.ui.fmd.render(txt4,True,dn["col"]);ts4.set_alpha(aa4)
                        if dn.get("scr"): self.screen.blit(ts4,(dn["x"]-ts4.get_width()//2,int(dn["y"]-dy4)))
                        else: self.screen.blit(ts4,(dn["x"]-ts4.get_width()//2-self.cam_x,int(dn["y"]-dy4)-self.cam_y))
                        alive_d.append(dn)
                    self.dmg_nums=alive_d
                    self.ps.draw(self.screen,self.cam_x,self.cam_y)
                    in_world=self.state in self.HUD_STATES
                    for _n in self.cur_map.npcs:
                        if npc_has_quest(_n.name,self.flags):
                            self.ui.draw_quest_marker(self.screen,_n.tx,_n.ty,
                                                      self.cam_x,self.cam_y,self.tick)
                    if self.state=="playing":
                        tgt=self._interact_target()
                        if tgt:
                            kind,obj=tgt
                            btx,bty=(obj.tx,obj.ty) if kind=="npc" else obj
                            self.ui.draw_interact_badge(self.screen,btx,bty,self.cam_x,self.cam_y,self.tick)
                    if in_world:
                        cq=quest_title(self.flags["ch"])
                        self.ui.draw_hud(self.screen,p,T_(self.cur_map.name),self.flags["ch"],cq,self.tick)
                        # Diyalog kutusu alt şeridi kaplıyor — yetenek çubuğunu gizle.
                        if self.state!="dialog":
                            self.ui.draw_ability_bar(self.screen,p.stats,self.tick)
                    # Bilgi pencereleri yalnızca oyun içindeyken; ölüm/zafer ekranını kapatmasınlar.
                    if in_world and self.levelup_timer>0:
                        self.ui.draw_levelup_popup(self.screen,p.stats.level,self.tick)
                    if in_world and self.ch_announce>0:
                        self.ui.draw_chapter(self.screen,self.flags["ch"],min(255,self.ch_announce*3))

                if self.state=="dialog":
                    lpp=4;pl=[dlg_line(e) for e in self.dlg_lines[self.dlg_page*lpp:(self.dlg_page+1)*lpp]]
                    total=(len(self.dlg_lines)+lpp-1)//lpp
                    self.ui.draw_dialog(self.screen,T_(self.dlg_npc.name) if self.dlg_npc else "?",pl,
                                        self.dlg_page+1,total,self.dlg_reveal)
                elif self.state=="inventory":
                    self.ui.draw_inventory(self.screen,self.player,self.inv_sel,self.inv_tab,self.tick,self.eq_sel)
                elif self.state=="quest_log":
                    self.ui.draw_quest_log(self.screen,self.flags,self.flags["ch"])
                elif self.state=="levelup_alloc":
                    self.ui.draw_stat_alloc(self.screen,self.player.stats,self.player.stats.skill_points,self.stat_sel,True,self.tick)
                elif self.state=="gameover":
                    self.ui.draw_gameover(self.screen)
                elif self.state=="victory":
                    self.ui.draw_victory(self.screen,self.tick)

            if self.trans_alpha>0: self.ui.draw_transition(self.screen,self.trans_alpha,T_(self.entering_name))
            # Pause overlay
            if self.pause_open and self.state=="playing":
                self.ui.draw_pause(self.screen,self.tick,self._pause_sel)
            # Settings overlay
            if self.settings_open:
                self.ui.draw_settings(self.screen,self.settings_sel,self.tick)
            # FPS göstergesi
            if CFG.show_fps:
                fps_val=int(self.clock.get_fps())
                fp=self.fps_font.render(f"FPS:{fps_val}",True,(100,200,100))
                self.screen.blit(fp,(SW-fp.get_width()-4,SH-fp.get_height()-4))
            # Mini görev yan paneli (sadece playing)
            if self.state=="playing" and self.player and not self.settings_open:
                self.ui.draw_mini_quests(self.screen,self.flags,self.player.stats.char_class)
            pygame.display.flip()

        pygame.quit();sys.exit()


if __name__=="__main__":
    print("="*56)
    print(f"  KARANLIK TAC'IN LANETI  v{VERSION}")
    print("  pip install pygame numpy  |  python pixel_rpg.py")
    print("  Yeni: Sinifa ozgun saldiri | Ekipman Sistemi")
    print("  Yeni: Gorunmez harita gecisleri | Genis orman")
    print(f"  Ayarlar: {SETTINGS_FILE}")
    print("="*56)
    Game().run()
