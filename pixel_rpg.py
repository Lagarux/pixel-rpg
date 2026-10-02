#!/usr/bin/env python3
"""
KARANLIK TAC'IN LANETI  v6.2  ─  2D Pixel RPG
pip install pygame  |  python pixel_rpg.py

Kontroller:
  WASD / Ok      -> Hareket        F11  -> Tam Ekran
  E              -> Konuş/Etkileşim  ESC -> Çık/Geri
  Space          -> Sınıfa Özel Saldırı
  1 2 3 4        -> Yetenek Kullan
  I              -> Envanter / Ekipman
  M              -> Mini Harita
  Q              -> Görev Günlüğü
  U              -> Nitelik Dağıtımı
  F1             -> Ayarlar
"""
import pygame, sys, math, random, os, json, zlib, array
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
VERSION = "6.2"
TITLE   = "Karanlik Tac'in Laneti"   # ASCII: pencere basligi ve dosya adlari icin

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
        "minimap": True, "tutorial_seen": False, "difficulty": "normal",
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

# ─── Ses Yöneticisi (Prosedürel ses üretimi — saf Python) ────────
class SoundManager:
    """Efektleri ve ambiyans müziğini çalışma anında sentezler.

    numpy gerekmiyor: PCM örnekleri stdlib `array` ile üretilip doğrudan
    `mixer.Sound(buffer=...)`e veriliyor. Böylece oyun ek bir bağımlılık
    istemiyor ve paketlenen sürüm küçük kalıyor.
    """
    _sounds:Dict={}
    _enabled=True
    SR=22050            # istenen örnekleme hızı
    _format=(22050,2)   # mixer'in GERÇEKTEN açtığı (hız, kanal) — init() günceller
    _fail=""            # son üretim hatası: sessiz kalmışsak nedeni burada

    @classmethod
    def _osc(cls,wave,freq,dur,vibrato=0.0,noise=0.0):
        """Dalga formunu -1..1 aralığında örnek listesine açar."""
        sr=cls._format[0]; n=max(1,int(sr*dur)); out=[0.0]*n
        tau=2.0*math.pi
        for k in range(n):
            t=k/sr; ph=freq*t
            if   wave=="square": v=(1.0 if math.sin(tau*ph)>=0.0 else -1.0)*0.5
            elif wave=="saw":    v=2.0*(ph-math.floor(ph+0.5))
            elif wave=="tri":    v=2.0*abs(2.0*(ph-math.floor(ph+0.5)))-1.0
            else:                v=math.sin(tau*ph)
            if vibrato>0.0: v*=math.sin(tau*vibrato*t)*0.1+0.9
            if noise>0.0:   v+=random.uniform(-noise,noise)
            out[k]=v
        return out

    @classmethod
    def _lowpass(cls,buf,hz):
        """Tek kutuplu alçak geçiren süzgeç: tiz harmonikleri yumuşatır.

        Testere ve gürültü dalgaları doğrudan kullanıldığında ses "tırmalıyor"
        — ölçtük: yürüme sesinin parlaklığı 0.76'ydı, diğerlerinin 0.2'si.
        """
        sr=cls._format[0]
        a=1.0-math.exp(-2.0*math.pi*float(hz)/sr)
        y=0.0
        for k in range(len(buf)):
            y+=a*(buf[k]-y); buf[k]=y
        return buf

    @classmethod
    def _fade(cls,buf,secs=0.006):
        """Başta/sonda kısa rampa — ani kesmenin çıkardığı 'tık' sesini önler."""
        n=len(buf); f=min(int(cls._format[0]*secs),n//2)
        for k in range(f):
            g=k/f; buf[k]*=g; buf[n-1-k]*=g
        return buf

    @classmethod
    def _envelope(cls,buf,attack,decay,vol):
        """Yükseliş/düşüş zarfını uygular."""
        sr=cls._format[0]; n=len(buf)
        att=min(int(sr*attack),n); dec=int(sr*decay)
        span=dec if (dec>0 and att+dec<n) else max(1,n-att)
        for k in range(n):
            if k<att:    e=k/att
            elif dec<=0: e=1.0
            else:
                d=k-att
                e=1.0-d/span if d<span else 0.0
                if e<0.0: e=0.0
            buf[k]*=e*vol
        return buf

    @classmethod
    def _pcm(cls,buf):
        """Örnek listesini mixer biçiminde (signed 16-bit) Sound'a çevirir."""
        chans=cls._format[1]; n=len(buf)
        pcm=array.array("h",bytes(2*chans*n))
        for k in range(n):
            v=buf[k]
            if   v> 1.0: v= 1.0
            elif v<-1.0: v=-1.0
            sm=int(v*32767); b=k*chans
            for c in range(chans): pcm[b+c]=sm
        return pygame.mixer.Sound(buffer=pcm.tobytes())

    @classmethod
    def _make(cls,freq,dur,wave="sine",attack=0.01,decay=0.1,vol=0.4,vibrato=0.0,
              noise=0.0,lp=None):
        """Tek notalı efekt üretir. lp: alçak geçiren süzgeç kesim frekansı."""
        try:
            buf=cls._osc(wave,freq,dur,vibrato,noise)
            if lp: buf=cls._lowpass(buf,lp)
            return cls._pcm(cls._envelope(buf,attack,decay,vol))
        except Exception as e:
            cls._fail="_make(%s): %s"%(freq,e); return None

    @classmethod
    def _chord(cls,freqs,dur,**kw):
        """Birkaç notayı üst üste bindirip akor üretir."""
        try:
            mix=cls._osc("sine",freqs[0],dur)
            for f in freqs[1:]:
                other=cls._osc("sine",f,dur)
                for k in range(len(mix)): mix[k]+=other[k]
            g=kw.get("vol",0.35)/len(freqs)
            for k in range(len(mix)): mix[k]*=g
            return cls._pcm(cls._fade(mix))
        except Exception as e:
            cls._fail="_chord(%s): %s"%(freqs,e); return None

    @classmethod
    def init(cls):
        try:
            pygame.mixer.init(frequency=cls.SR,size=-16,channels=2,buffer=512)
            got=pygame.mixer.get_init()
        except Exception as e:
            cls._enabled=False; cls._fail="mixer.init: %s"%e; return
        if not got:
            cls._enabled=False; cls._fail="mixer açılamadı"; return
        if got[1]!=-16:   # sentezimiz signed 16-bit üretiyor
            cls._enabled=False; cls._fail="beklenmeyen örnek biçimi: %s"%(got[1],); return
        cls._format=(got[0],max(1,got[2]))
        defs={
            # Tiz harmonikler süzülüyor: ölçülen parlaklık 0.43/0.53 idi.
            "hit":      lambda: cls._make(200,0.12,"saw",0.006,0.11,0.46,noise=0.16,lp=2000),
            "hit_heavy":lambda: cls._make(140,0.20,"saw",0.008,0.18,0.55,noise=0.22,lp=1400),
            "heal":     lambda: cls._chord([523,659,784],0.35,vol=0.4),
            "level_up": lambda: cls._chord([261,329,392,523,659,784],0.9,vol=0.5),
            "chest":    lambda: cls._chord([392,494,587,784],0.5,vol=0.4),
            # Yürüme her adımda çalıyor: en sert ses buydu (parlaklık 0.76).
            # Daha pes, daha kısık, iyice süzülmüş bir "pat" sesi.
            "walk":     lambda: cls._make(110,0.05,"sine",0.002,0.045,0.16,noise=0.30,lp=700),
            "spell":    lambda: cls._chord([440,554,659],0.25,vol=0.45),
            "arrow":    lambda: cls._make(520,0.10,"tri",0.003,0.09,0.28,noise=0.05,lp=3000),
            "menu_sel": lambda: cls._make(660,0.08,"sine",0.005,0.07,0.3),
            "menu_back":lambda: cls._make(440,0.08,"sine",0.005,0.07,0.25),
            "boss_alert":lambda: cls._chord([110,138,165],0.8,vol=0.55),
            "victory":  lambda: cls._chord([523,659,784,1046],1.2,vol=0.5),
            "death":    lambda: cls._chord([110,138],0.8,vol=0.45),
            "equip":    lambda: cls._chord([330,415,494],0.25,vol=0.35),
            "error":    lambda: cls._make(190,0.18,"tri",0.006,0.15,0.30,lp=1800),
            "open_ui":  lambda: cls._chord([392,494,587],0.18,vol=0.3),
            "trap":     lambda: cls._make(320,0.15,"tri",0.006,0.12,0.38,noise=0.10,lp=2200),
            "freeze":   lambda: cls._chord([880,1108,1318],0.3,vol=0.35),
        }
        for k,fn in defs.items():
            try:
                s=fn()
                if s: cls._sounds[k]=s
                else: cls._fail=cls._fail or "%s: üretilemedi"%k
            except Exception as e: cls._fail="%s: %s"%(k,e)
        if not cls._sounds:   # sessizce susmak yerine nedenini söyle
            cls._enabled=False
            print("[ses] hicbir ses uretilemedi, oyun sessiz devam ediyor:",
                  cls._fail, file=sys.stderr)

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

        Üretilen parça önbelleğe alınır: harita geçişinde yeniden
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
            # Her temaya özel nota dizisi, süre, dalga ve ses seviyesi
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
            loop = []
            for freq in notes:                       # notaları sırayla ekle
                seg = cls._osc(wave, freq, dur)
                for k in range(len(seg)): seg[k] *= vol
                loop.extend(cls._fade(seg, 0.06))    # notalar arası tık olmasın
            snd = cls._pcm(loop)
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

    # ── Ara ve üst kademe ────────────────────────────────────────
    # Eskiden her sınıfın iki silahı vardı ve ikisi de sandıklardan
    # çıkıyordu: dükkâna gitmenin bir sebebi yoktu. Üst kademe yalnızca
    # satın alınır ve demircide yükseltilir.
    "war_axe":      ("Savaş Baltası",(190,90,60), {"str":5,"vit":1}, "weapon", {"warrior"}),
    "crown_blade":  ("Taç Kılıcı",   (240,210,120),{"str":9,"vit":2},"weapon", {"warrior"}),
    "hunter_bow":   ("Avcı Yayı",    (140,180,90),{"agi":4,"vit":1}, "weapon", {"archer"}),
    "storm_bow":    ("Fırtına Yayı", (120,200,240),{"agi":7,"str":3},"weapon", {"archer"}),
    "ember_rod":    ("Köz Asası",    (230,120,60),{"int":5},         "weapon", {"mage"}),
    "void_staff":   ("Boşluk Asası", (120,60,180),{"int":9,"wis":2}, "weapon", {"mage"}),
    "oak_staff":    ("Meşe Asa",     (150,120,70),{"wis":3,"int":1}, "weapon", {"healer"}),
    "dawn_scepter": ("Şafak Asası",  (255,230,150),{"wis":6,"int":4},"weapon", {"healer"}),

    "chain_mail":   ("Zincir Zırh",  (150,150,160),{"vit":3},        "armor",  None),
    "guardian_plate":("Muhafız Plakası",(200,200,215),{"vit":7,"str":2},"armor",{"warrior"}),
    "arch_robe":    ("Baş Büyücü Cübbesi",(120,90,220),{"int":5,"wis":3},"armor",{"mage"}),
    "ranger_cloak": ("Korucu Pelerini",(80,140,90),{"agi":5,"vit":2},"armor", {"archer"}),
    "saint_robe":   ("Aziz Cübbesi", (255,240,200),{"wis":5,"vit":3},"armor", {"healer"}),

    "travel_boots": ("Yolcu Botu",   (140,110,70),{"vit":1,"agi":1}, "boots",  None),
    "wind_greaves": ("Rüzgâr Dizliği",(150,230,200),{"agi":5,"vit":1},"boots", None),

    "ruby_ring":    ("Yakut Yüzük",  (220,60,60), {"str":3,"int":1}, "ring",   None),
    "jade_ring":    ("Yeşim Yüzük",  (80,200,120),{"vit":2,"wis":2}, "ring",   None),
    "obsidian_ring":("Obsidyen Yüzük",(90,70,110),{"str":2,"int":2,"agi":1},"ring",None),

    "moon_pendant": ("Ay Kolyesi",   (200,220,255),{"wis":3,"int":2},"amulet", None),
    "ember_charm":  ("Köz Tılsımı",  (240,140,60),{"str":3,"vit":1}, "amulet", None),
    "sage_talisman":("Bilge Tılsımı",(180,160,240),{"wis":4,"int":2},"amulet", None),
}

# Ekipman yuvalarının sabit sırası — envanter imleci ve çizim bunu paylaşır.
# NOT: Önceden bot, yüzük, muska ve nişanların HEPSİ tek "ring" yuvasındaydı;
# mana taşı takınca hız botu çıkıyordu. Yuvalar türe göre ayrıldı.
EQUIP_SLOTS = ("weapon","armor","boots","ring","amulet")
SLOT_NAMES  = {"weapon":"Silah","armor":"Zirh","boots":"Bot","ring":"Yuzuk","amulet":"Muska"}
SLOT_COLORS = {"weapon":UI_RD,"armor":ST_L,"boots":G_L,"ring":UI_GD,"amulet":UI_CY}

ITEMS = {
    "hp_pot": ("Sağlık İksiri", HP_G,   "heal",   35,  "35 HP iyileştirir."),
    "mp_pot": ("Mana İksiri",   MP_B,   "mana",   25,  "25 MP iyileştirir."),
    "gold":   ("Altın",         UI_GD,  "gold",    5,  "Değerli para."),
    "earth_c":("Toprak Kristali",(120,200,80),"quest",0,"Antik kristal."),
    "water_c":("Su Kristali",  (80,180,220),"quest",0,"Antik kristal."),
    "fire_c": ("Ateş Kristali",(250,130,50), "quest",0,"Antik kristal."),
    "light_c":("Işık Kristali",(250,230,150),"quest",0,"Antik kristal."),
    "farm_tool":("Çiftçi Aleti",(140,100,60),"stat_str",1,"STR +1 kalıcı."),
    "river_gem":("Nehir Taşı", (60,180,200),"stat_wis",1,"WIS +1 kalıcı."),
    "scroll1":  ("Karanlık Parşömen",(180,140,220),"quest_sq",0,"Gizemli parşömen 1/3."),
    "scroll2":  ("Ateş Parşömeni",  (220,140,80), "quest_sq",0,"Gizemli parşömen 2/3."),
    "scroll3":  ("Buz Parşömeni",   (140,200,220),"quest_sq",0,"Gizemli parşömen 3/3."),

    # ── Büyük iksirler ve tonikler ───────────────────────────────
    # Tek bir sağlık iksiri vardı ve 54 tanesi sandıklardan bedava
    # çıkıyordu. Artık kademeli: küçük iksir ucuz ve bol, büyüğü pahalı.
    "hp_pot_l":  ("Büyük Sağlık İksiri",(120,230,120),"heal",  90,"90 HP iyileştirir."),
    "mp_pot_l":  ("Büyük Mana İksiri", (120,170,255),"mana",   70,"70 MP iyileştirir."),
    "elixir":    ("Tam Şifa İksiri",   (255,225,140),"full",    0,"Canı ve manayı tam doldurur."),
    "tonic_str": ("Güç Toniği",        (225,110,60), "buff_str",900,"15 saniye saldırı +%40."),
    "tonic_def": ("Taş Derisi",        (160,160,172),"buff_def",900,"15 saniye gelen hasar -%30."),
    "tonic_swift":("Rüzgâr Toniği",    (130,225,170),"buff_agi",900,"15 saniye hız ve kritik artar."),

    # ── Kalıcı nitelik taşları (boss ödülü) ──────────────────────
    "oracle_lens":("Kâhin Merceği",   (150,110,220),"stat_int",1,"INT +1 kalıcı."),
    "titan_core": ("Titan Çekirdeği", (190,170,140),"stat_vit",1,"VIT +1 kalıcı."),
    "wind_feather":("Rüzgâr Tüyü",    (180,230,200),"stat_agi",1,"AGI +1 kalıcı."),
}

# ─── Malzemeler ──────────────────────────────────────────────────
# Düşmanlardan düşer, satılır ve demircide yükseltmeye harcanır.
# Oyunun tek altın kaynağı "öldür, 1-4 altın al" idi; artık avlanmanın
# kendisi bir gelir ve bir üretim zinciri.
# anahtar -> (ad, renk, satış değeri, hangi türden düşer)
MATERIALS = {
    "slime_jelly":  ("Yeşil Öz",        (110,210,110),  8, "slime"),
    "bat_wing":     ("Yarasa Kanadı",   (120,100,140), 10, "bat"),
    "beast_pelt":   ("Hayvan Postu",    (160,120,80),  13, "wolf"),
    "boar_tusk":    ("Domuz Dişi",      (230,225,205), 15, "boar"),
    "goblin_charm": ("Goblin Muskası",  (150,180,110), 14, "goblin"),
    "spider_silk":  ("Örümcek İpeği",   (225,225,235), 19, "spider"),
    "bone_dust":    ("Kemik Tozu",      (220,215,200), 17, "skeleton"),
    "venom_sac":    ("Zehir Kesesi",    (190,210,70),  21, "scorpion"),
    "bandit_coin":  ("Haydut Kesesi",  (215,180,90),  24, "bandit"),
    "iron_ore":     ("Demir Cevheri",   (140,140,150), 26, "golem"),
    "heart_wood":   ("Kalp Odunu",      (120,160,80),  29, "treant"),
    "frost_shard":  ("Ayaz Kırığı",     (170,220,250), 31, "ice_wolf"),
    "ember_core":   ("Köz Çekirdeği",   (240,130,50),  36, "lava_imp"),
    "ghost_veil":   ("Hayalet Tülü",    (200,200,230), 38, "wraith"),
    "shadow_shard": ("Gölge Kırığı",    (170,100,220), 44, "shadow_knight"),
}
for _k,(_ad,_c,_deger,_tur) in MATERIALS.items():
    ITEMS[_k]=(_ad,_c,"material",_deger,"Malzeme — satılır ya da yükseltmede kullanılır.")

# Hangi tür hangi malzemeyi düşürür
DROP_BY_KIND = {tur:k for k,(_a,_c,_d,tur) in MATERIALS.items()}
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
    2:("Ormanin Sirri",    "Karanlik Ormanda Sor Roland'i bul."),
    3:("Toprak Kristali",  "Antik Harabelerde Toprak Kristalini al."),
    4:("Kahin Kehaneti",   "Colde Oracle Nyx'i bul."),
    5:("Buzun Kalbi",      "Buz Magarasinda Su Kristalini al."),
    6:("Son Savas",        "Golge Kalesinde Malachar'i yen!"),
}



# ─── Düşman davranışları ─────────────────────────────────────────
# Önceden bütün düşmanlar aynı şekilde kovalıyordu; çizimleri farklı
# olsa da oynanışta hepsi aynıydı. Artık her türün bir davranışı var.
#   melee   : yanaşıp vurur (varsayılan)
#   ranged  : uzaktan mermi atar, oyuncu yaklaşırsa geri çekilir
#   skittish: canı azalınca kaçar
#   pack    : yalnızken çekingen, yanında dostu varken cesur
BEHAVIORS = {
    "slime":        {"type":"melee"},
    "goblin":       {"type":"skittish","flee_hp":0.3},
    "skeleton":     {"type":"melee"},
    "wolf":         {"type":"pack","pack_range":6},
    "ice_wolf":     {"type":"pack","pack_range":6},
    "boar":         {"type":"melee"},
    "golem":        {"type":"melee"},
    "scorpion":     {"type":"ranged","range":5,"cool":95,"proj":"shadow_bolt"},
    "shadow_knight":{"type":"melee"},
    "malachar":     {"type":"ranged","range":7,"cool":70,"proj":"shadow_bolt","melee_too":True},
    # ── Yeni türler ──────────────────────────────────────────────
    "bat":          {"type":"melee"},                      # hızlı, cılız
    "spider":       {"type":"ranged","range":4,"cool":110,"proj":"web","melee_too":True},
    "bandit":       {"type":"skittish","flee_hp":0.18},    # son anda kaçar
    "wraith":       {"type":"ranged","range":6,"cool":85,"proj":"shadow_bolt"},
    "treant":       {"type":"melee"},                      # yavaş, çok dayanıklı
    "lava_imp":     {"type":"skittish","flee_hp":0.35},
    # ── Kristal muhafızları ─────────────────────────────────────
    "ember_titan":  {"type":"ranged","range":5,"cool":80,"proj":"fireball",
                     "melee_too":True},
    "page_warden":  {"type":"ranged","range":7,"cool":75,"proj":"web",
                     "melee_too":True},
}

# Tür başına hareket hızı düzeltmesi (kare cinsinden bekleme; eksi = hızlı).
# Eskiden bu, AI döngüsünün içine elle yazılmış iki if idi.
SPEED_MOD = {
    "wolf":-4, "ice_wolf":-4, "golem":+8, "treant":+10,
    "bat":-6, "spider":-2, "bandit":-2, "lava_imp":-3, "wraith":+1,
    "ember_titan":+4, "page_warden":+2,
}

# ─── Zorluk seviyeleri ───────────────────────────────────────────
# Çarpanlar düşman kurulurken değil, hasar HESAPLANIRKEN uygulanıyor.
# Böylece zorluk oyunun ortasında değiştirilebiliyor ve kayıtlı bir oyun
# hangi zorlukta yüklenirse yüklensin tutarlı kalıyor — düşmanların can
# değerlerine dokunsaydık yüklemede eski değerler kalırdı.
DIFFICULTIES = [
    # id,          ad anahtarı,        vurduğun, yediğin, altın, xp,  kalıcı ölüm
    # Kolay ödülü arttırmıyor, yalnızca dövüşü kolaylaştırıyor: aksi hâlde
    # "zor olan çok kazandırır" kuralı bozulurdu.
    ("easy",       "ui.diff_easy",     1.25, 0.65, 1.00, 1.00, False),
    ("normal",     "ui.diff_normal",   1.00, 1.00, 1.00, 1.00, False),
    ("hard",       "ui.diff_hard",     0.85, 1.35, 1.15, 1.20, False),
    ("brutal",     "ui.diff_brutal",   0.72, 1.75, 1.30, 1.40, False),
    ("hardcore",   "ui.diff_hardcore", 0.62, 2.10, 1.50, 1.60, True),
]
DIFF_IDS  = [d[0] for d in DIFFICULTIES]
DIFF_COL  = {"easy":(120,210,120),"normal":(200,200,210),"hard":(240,195,90),
             "brutal":(240,125,70),"hardcore":(235,70,70)}
DIFF_DESC = {d[0]:d[1]+"_desc" for d in DIFFICULTIES}


def difficulty(did=None):
    """Seçili zorluk satırı; tanınmayan değer gelirse Orta."""
    did = did or CFG.data.get("difficulty","normal")
    for d in DIFFICULTIES:
        if d[0]==did: return d
    return DIFFICULTIES[1]


def diff_mult(key)->float:
    d=difficulty()
    return {"player_dmg":d[2],"enemy_dmg":d[3],"gold":d[4],"xp":d[5]}[key]


def diff_permadeath()->bool:
    return bool(difficulty()[6])


def diff_name(did=None)->str:
    return T_(difficulty(did)[1])


# ─── Elementler ──────────────────────────────────────────────────
# Her düşmanın bir elementi var; her saldırının da. Çarpan tablosu ikisini
# karşılaştırıyor: doğru elementle vurmak ödüllendiriyor, yanlışıyla vurmak
# düşmanı belirgin biçimde dayanıklı yapıyor. Zorluk buradan geliyor —
# düşmanlara sadece HP eklemek dövüşü uzatır, ilginç yapmaz.
ELEMENTS = ("physical", "fire", "ice", "nature", "shadow", "holy", "earth")

ELEM_NAMES = {"physical":"ui.elem_physical","fire":"ui.elem_fire","ice":"ui.elem_ice",
              "nature":"ui.elem_nature","shadow":"ui.elem_shadow","holy":"ui.elem_holy",
              "earth":"ui.elem_earth"}
ELEM_COL = {"physical":(200,200,205),"fire":(255,110,50),"ice":(120,200,255),
            "nature":(120,210,110),"shadow":(170,100,220),"holy":(255,225,120),
            "earth":(190,150,90)}

# saldiri elementi -> hedef elementi -> carpan (yazilmayan = 1.0)
ELEM_CHART = {
    # Fiziksel nötr: herkesin elinde olan temel saldırı cezalandırılmıyor.
    # Savaşçı ve okçu gölge düşmanlara karşı çaresiz kalmasın diye.
    "physical": {},
    "fire":     {"nature":1.60, "ice":1.60, "fire":0.40, "earth":0.80},
    "ice":      {"nature":1.50, "earth":1.25, "fire":0.50, "ice":0.40},
    "nature":   {"earth":1.60, "shadow":1.30, "nature":0.50, "fire":0.60},
    "shadow":   {"holy":1.60, "nature":1.30, "physical":1.25, "shadow":0.40},
    "holy":     {"shadow":1.80, "physical":1.10, "holy":0.50},
    "earth":    {"fire":1.40, "physical":1.15, "nature":0.60, "earth":0.50},
}

# İki kareye sığmayan, 2x2 çizilen dev boss'lar
BIG_SPRITES = ("malachar","ember_titan","page_warden")

ENEMY_ELEM = {
    "slime":"nature", "boar":"nature", "wolf":"physical", "goblin":"physical",
    "skeleton":"shadow", "golem":"earth", "scorpion":"fire", "ice_wolf":"ice",
    "shadow_knight":"shadow", "malachar":"shadow",
    "bat":"shadow", "spider":"nature", "bandit":"physical",
    "wraith":"shadow", "treant":"nature", "lava_imp":"fire",
    "ember_titan":"fire", "page_warden":"holy",
}

CLASS_ELEM = {"warrior":"physical", "archer":"physical", "mage":"fire", "healer":"holy"}

ABILITY_ELEM = {
    "shield_bash":"physical", "whirlwind":"physical", "earthquake":"earth",
    "freeze":"ice", "meteor":"fire", "arcane_nova":"shadow",
    "multi_shot":"physical", "trap":"physical", "rain_arrows":"physical",
    "shadow_step":"shadow", "divine_storm":"holy",
}

PROJ_ELEM = {"arrow":"physical", "shadow_bolt":"shadow", "web":"nature",
             "fireball":"fire"}

# Silahın elementi temel saldırıya geçiyor: doğru silahı almak işe yarasın.
WEAPON_ELEM = {
    "iron_sword":"physical", "steel_sword":"physical",
    "fine_bow":"physical",   "shadow_bow":"shadow",
    "arcane_staff":"fire",   "elder_staff":"ice",
    "holy_scepter":"holy",
    "war_axe":"physical",    "crown_blade":"holy",
    "hunter_bow":"physical", "storm_bow":"ice",
    "ember_rod":"fire",      "void_staff":"shadow",
    "oak_staff":"nature",    "dawn_scepter":"holy",
}

# Zırh ve muskalar bir elemente karşı koruma veriyor: hangi bölgeye
# gittiğine göre ekipman seçmek anlam kazansın.
EQUIP_RESIST = {
    "leather_armor":("nature",0.80), "plate_mail":("physical",0.75),
    "mage_robe":("fire",0.75),       "healer_robe":("shadow",0.75),
    "scout_coat":("ice",0.80),       "mana_gem":("ice",0.85),
    "warrior_crest":("physical",0.85), "archer_token":("nature",0.85),
    "mage_focus":("fire",0.85),      "power_ring":("earth",0.85),
    "chain_mail":("physical",0.82),  "guardian_plate":("earth",0.70),
    "arch_robe":("fire",0.70),       "ranger_cloak":("nature",0.72),
    "saint_robe":("shadow",0.68),    "travel_boots":("earth",0.90),
    "wind_greaves":("ice",0.80),     "ruby_ring":("fire",0.80),
    "jade_ring":("nature",0.80),     "obsidian_ring":("shadow",0.82),
    "moon_pendant":("holy",0.80),    "ember_charm":("fire",0.78),
    "sage_talisman":("shadow",0.80),
}

# Düşman dayanıklılığı: bazı türler 2 vuruşta ölüyordu. Çarpanları tek
# yerde tutuyoruz ki her Enemy(...) satırını elle düzeltmek gerekmesin.
# Fark etme (agro) ve kovalamayı bırakma mesafeleri — kare cinsinden.
# Eskiden her Enemy(...) satırında elle yazılıyordu ve 4-7 arasında dağınıktı:
# golem aynı haritada 4, 5, 6 ve 7 ile doğuyordu. Daha kötüsü akrep 5 kareden
# ateş ettiği hâlde ancak 5-6 karede fark ediyor, mevzi alamadan menzile
# giriyordu. Artık tür bazında ve davranışla tutarlı.
AGGRO = {
    "slime":         (4,  7),   # yavaş, geç fark eder, çabuk bırakır
    "boar":          (5,  9),   # yakından irkilir, kısa mesafe kovalar
    "goblin":        (7,  9),   # çabuk fark eder, canı azalınca kaçar
    "wolf":          (8, 13),   # kokuyla avlanır: erken fark eder, inat eder
    "ice_wolf":      (8, 13),
    "skeleton":      (6, 10),
    "scorpion":      (9, 12),   # atış menzili 5; mevzi alabilmek için uzaktan fark eder
    "golem":         (5, 15),   # geç fark eder ama bir kez uyandı mı bırakmaz
    "shadow_knight": (7, 11),
    "malachar":     (12, 99),   # boss: oda sınırları içinde her zaman takip eder
    "bat":           (7, 11),   # kanat sesini duyar duymaz üstüne gelir
    "spider":        (6, 10),   # ağına yaklaşılmasını bekler
    "bandit":        (9, 14),   # yol kesicidir: uzaktan seçer, uzun kovalar
    "wraith":       (10, 14),   # menzili 6; mevzi alabilsin diye erken fark eder
    "treant":        (4, 10),   # uyandırana kadar ağaç sanırsın; ok kadar yavaş
                                # olduğu için uzun kovalamanın anlamı yok
    "lava_imp":      (7, 10),
    "ember_titan":  (10, 40),   # boss: vadinin ortasinda, odasini birakmaz
    "page_warden":  (10, 40),
}

ENEMY_TUNE = {   # tür -> (HP çarpanı, saldırı çarpanı)
    "slime":(1.75,1.20), "wolf":(1.40,1.05), "boar":(1.35,1.05),
    "goblin":(1.45,1.05), "skeleton":(1.30,1.00), "scorpion":(1.30,1.00),
    "ice_wolf":(1.30,1.00), "golem":(1.25,1.00), "shadow_knight":(1.30,1.05),
    "malachar":(1.25,1.05),
    # Yarasanın kimliği "az can" değil "hızlı ve küçük":
    # 0.70 çarpanıyla 1. seviyede TEK vuruşta ölüyordu.
    "bat":(1.80,0.80), "spider":(1.15,1.05), "bandit":(1.20,1.20),
    "wraith":(1.05,1.15), "treant":(2.10,1.25), "lava_imp":(0.95,1.15),
    "ember_titan":(1.30,1.10), "page_warden":(1.25,1.10),
}


def elem_mult(saldiri, hedef) -> float:
    """Saldırı elementinin hedef elementine karşı çarpanı."""
    return ELEM_CHART.get(saldiri, {}).get(hedef, 1.0)


def elem_name(key) -> str:
    return T_(ELEM_NAMES.get(key, "ui.elem_physical"))


def game_title()->str:
    """Ekranda gösterilen başlık. TITLE sabiti ASCII (pencere başlığı için);
    oyuncunun gördüğü başlık Türkçe karakterleri ve çeviriyi kullanıyor."""
    return T_("ui.game_title",default="Karanlık Taç'ın Laneti")


def behavior(kind)->Dict:
    return BEHAVIORS.get(kind,{"type":"melee"})

# ─── Ekonomi ─────────────────────────────────────────────────────
# Altın toplanıyordu ama harcanacak yer yoktu. Fiyatlar başlangıç
# altınına (20) ve yan görev ödüllerine (40-120) göre ayarlandı.
ITEM_PRICES = {
    "hp_pot":28,"mp_pot":34,"hp_pot_l":80,"mp_pot_l":95,"elixir":210,
    "tonic_str":120,"tonic_def":120,"tonic_swift":130,
    "iron_sword":110,"steel_sword":260,"fine_bow":120,"shadow_bow":280,
    "arcane_staff":115,"elder_staff":270,"holy_scepter":130,
    "leather_armor":85,"plate_mail":240,"mage_robe":95,"healer_robe":100,"scout_coat":105,
    "swift_boots":90,"power_ring":95,"mage_focus":110,"mana_gem":100,
    "warrior_crest":115,"archer_token":105,
    "farm_tool":140,"river_gem":150,      # kalıcı nitelik veriyorlar, pahalı
    # Ara kademe
    "war_axe":190,"hunter_bow":195,"ember_rod":190,"oak_staff":150,
    "chain_mail":170,"travel_boots":120,"ruby_ring":180,"jade_ring":180,
    "moon_pendant":190,"ember_charm":185,
    # Üst kademe — yalnızca satın alınır, sandıktan çıkmaz
    "crown_blade":820,"storm_bow":840,"void_staff":860,"dawn_scepter":800,
    "guardian_plate":720,"arch_robe":700,"ranger_cloak":690,"saint_robe":700,
    "wind_greaves":560,"obsidian_ring":600,"sage_talisman":620,
}
SELL_RATE = 0.4     # satarken alınan oran (dükkân kâr eder)
REST_PRICE = 18     # handa konaklama

# ─── Ekipman yükseltme ───────────────────────────────────────────
# Altının harcanacak yeri yoktu: ölçümde oyunda toplanabilecek 1730 altına
# karşılık mağazadaki 22 eşyanın 19'u sandıklardan bedava çıkıyordu.
# Yükseltme hem altını hem de avlanarak toplanan malzemeyi tüketiyor.
UPGRADE_MAX = 5
UPGRADE_COST = [(60,2),(140,3),(280,4),(500,5),(850,6)]   # (altın, malzeme)
# Tek bir parçayı sonuna kadar yükseltmek: 1830 altın + 20 malzeme.

# Düşman başına malzeme düşme olasılığı. Boss her zaman düşürür.
MAT_DROP_CHANCE = 0.45

# Ölen düşman kaç karede geri doğar (60 fps). Oyuncu 14 kareden yakınsa
# beklemeye devam eder: gözünün önünde belirmesin.
RESPAWN_FRAMES = 3600
RESPAWN_MIN_DIST = 14

# Seviye tavanı. Düşmanlar geri doğduğu için XP artık sınırsız; eskiden
# oyunun tamamı 5368 XP veriyordu ve içerik seviye 10'da bitiyordu.
MAX_LEVEL = 30

# Deneyim eğrisi. Eşik her seviyede 1.55 ile çarpılıyordu; bu, oyunun
# tamamı 5368 XP verdiği için sorun değildi ama 30. seviye 29,6 MİLYON XP
# demek oluyordu — ulaşılamaz bir tavan tavan değildir. İlk yedi seviye
# aynı hızda kalıyor (hikâyenin temposu bozulmasın), sonrası yumuşuyor.
XP_EARLY = 1.55
XP_LATE  = 1.15
XP_KNEE  = 8


def xp_to_next(level)->int:
    """level seviyesinden bir sonrakine geçmek için gereken XP."""
    if level < XP_KNEE:
        return int(50*(XP_EARLY**(level-1)))
    return int(50*(XP_EARLY**(XP_KNEE-1))*(XP_LATE**(level-XP_KNEE)))


def upgrade_bonus(item_k,lvl,stat)->int:
    """Yükseltmenin bir niteliğe kattığı miktar.

    Parçanın en güçlü niteliği her kademede +1, ikinci niteliği iki
    kademede +1 alıyor: kılıç yükseltilince kılıç kalıyor.
    """
    if lvl<=0 or item_k not in EQUIP_ITEMS: return 0
    bonus=EQUIP_ITEMS[item_k][2]
    if not bonus: return 0
    sirali=sorted(bonus,key=lambda k:(-bonus[k],k))
    if stat==sirali[0]: return lvl
    if len(sirali)>1 and stat==sirali[1]: return lvl//2
    return 0


def upgrade_cost(lvl):
    """lvl kademesinden bir sonrakine geçmenin bedeli, ya da None."""
    if lvl>=UPGRADE_MAX: return None
    return UPGRADE_COST[lvl]

def item_price(key)->int:
    return ITEM_PRICES.get(key,20)

def sell_price(key)->int:
    # Malzemenin satış değeri doğrudan yazılı: alış fiyatı yok, çünkü
    # satın alınmıyor — avlanarak toplanıyor.
    if key in MATERIALS: return MATERIALS[key][2]
    return max(1,int(item_price(key)*SELL_RATE))

# Hangi NPC neyi satıyor
SHOPS = {
    # Demirci: bütün kademeler + yükseltme tezgâhı. Üst kademe (crown_blade,
    # storm_bow, void_staff, dawn_scepter ve zırhları) hiçbir sandıktan
    # çıkmıyor; yalnızca burada satılıyor.
    "npc.demirci_boran":{
        "stock":["iron_sword","war_axe","steel_sword","crown_blade",
                 "fine_bow","hunter_bow","shadow_bow","storm_bow",
                 "arcane_staff","ember_rod","elder_staff","void_staff",
                 "oak_staff","holy_scepter","dawn_scepter",
                 "leather_armor","chain_mail","plate_mail","guardian_plate",
                 "mage_robe","arch_robe","healer_robe","saint_robe",
                 "scout_coat","ranger_cloak"],
        "rest":False,"upgrade":True,
    },
    "npc.hanci_mira":{
        "stock":["hp_pot","hp_pot_l","mp_pot","mp_pot_l","elixir",
                 "swift_boots","travel_boots","power_ring","mana_gem"],
        "rest":True,
    },
    # ── Pazar tezgâhları ──
    "npc.otaci_nesrin":{"stock":["hp_pot","hp_pot_l","mp_pot","mp_pot_l","elixir",
                                 "tonic_str","tonic_def","tonic_swift",
                                 "river_gem"],"rest":False},
    "npc.avci_doruk":{"stock":["fine_bow","hunter_bow","shadow_bow","storm_bow",
                               "scout_coat","ranger_cloak","archer_token",
                               "wind_greaves"],"rest":False},
    "npc.tuccar_salim":{"stock":["swift_boots","travel_boots","wind_greaves",
                                 "power_ring","ruby_ring","jade_ring","obsidian_ring",
                                 "mana_gem","moon_pendant","ember_charm",
                                 "sage_talisman","mage_focus","warrior_crest"],
                        "rest":False},
    "npc.ciftci_hale":{"stock":["farm_tool","hp_pot","hp_pot_l","tonic_str"],
                       "rest":False},
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
    {"id":"slime",   "title":"ui.sq_slime",   "desc":"ui.sq_slime_desc",
     "unit":"ui.unit_slime","col":(120,200,140),
     "progress":lambda f: (min(5,f.get("kill_slime",0)),5),
     "gold":45,"xp":40},
    {"id":"goblin",  "title":"ui.sq_goblin",  "desc":"ui.sq_goblin_desc",
     "unit":"ui.unit_goblin","col":(150,190,110),
     "progress":lambda f: (min(6,f.get("kill_goblin",0)),6),
     "gold":75,"xp":70},
    {"id":"chest",   "title":"ui.sq_chest",   "desc":"ui.sq_chest_desc",
     "unit":"ui.unit_chest","col":UI_GD,
     "progress":lambda f: (min(8,f.get("chests_opened",0)),8),
     "gold":100,"xp":80},
    {"id":"scorpion","title":"ui.sq_scorpion","desc":"ui.sq_scorpion_desc",
     "unit":"ui.unit_scorpion","col":(210,170,90),
     "progress":lambda f: (min(3,f.get("kill_scorpion",0)),3),
     "gold":110,"xp":100},
    {"id":"icewolf", "title":"ui.sq_icewolf", "desc":"ui.sq_icewolf_desc",
     "unit":"ui.unit_icewolf","col":(170,220,250),
     "progress":lambda f: (min(3,f.get("kill_ice_wolf",0)),3),
     "gold":130,"xp":120},
    {"id":"knight",  "title":"ui.sq_knight",  "desc":"ui.sq_knight_desc",
     "unit":"ui.unit_knight","col":(190,120,220),
     "progress":lambda f: (min(3,f.get("kill_shadow_knight",0)),3),
     "gold":180,"xp":180},
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

# ─── Ana bossler ve kapanış sahneleri ────────────────────────────
# Malachar dışındaki boss'lar sessizce ölüyordu: dev bir yaratığı
# devirmek, bir sıçanı devirmekle aynı hissi veriyordu. Artık her ana
# boss düştüğünde araya bir sahne giriyor — mührün bir parçası
# kırılıyor, karanlıktan bir pay geri alınıyor.
#
# Hikâyede dört kristalden söz ediliyordu ama oyunda yalnızca ikisi
# vardı (toprak ve su). Köz Vadisi ile Gizemli Kütüphane'ye birer
# muhafız kondu: ateş ve ışık kristalleri. İkisi de isteğe bağlı —
# ana zinciri kilitlemiyor, eski kayıtları bozmuyor — ama kapanışa
# kendi sahnesini ekliyor ve unvanı yükseltiyor.
BOSSES = {
    "earth": {"kind":"golem", "map":"ruins", "crystal":"earth_c",
              "name":"boss.earth.name", "col":(150,200,90),
              "lines":["boss.earth.1","boss.earth.2","boss.earth.3","boss.earth.4"]},
    "water": {"kind":"golem", "map":"ice_cave", "crystal":"water_c",
              "name":"boss.water.name", "col":(120,200,245),
              "lines":["boss.water.1","boss.water.2","boss.water.3","boss.water.4"]},
    "fire":  {"kind":"ember_titan", "map":"ember_valley", "crystal":"fire_c",
              "name":"boss.fire.name", "col":(250,130,50),
              "lines":["boss.fire.1","boss.fire.2","boss.fire.3","boss.fire.4"]},
    "light": {"kind":"page_warden", "map":"mystic_library", "crystal":"light_c",
              "name":"boss.light.name", "col":(250,230,150),
              "lines":["boss.light.1","boss.light.2","boss.light.3","boss.light.4"]},
    "malachar":{"kind":"malachar", "map":"shadow_castle", "crystal":None,
                "name":"boss.malachar.name", "col":(190,110,245),
                "lines":["boss.malachar.1","boss.malachar.2",
                         "boss.malachar.3","boss.malachar.4"]},
}

# Kristal -> (bayrak, hangi nitelikleri kalıcı arttırır)
CRYSTAL_FLAG = {
    "earth_c":("earth_crystal",{}),
    "water_c":("water_crystal",{}),
    "fire_c": ("fire_crystal", {"str":1,"vit":1}),
    "light_c":("light_crystal",{"wis":1,"int":1}),
}


# ─── Kapanış ─────────────────────────────────────────────────────
# Malachar düşünce oyun doğrudan zafer ekranına atlıyordu. Kapanış bir
# oyunun en çok hatırlanan yeri; burada sayfa sayfa anlatılıyor ve oyuncunun
# NE YAPTIĞINA göre değişiyor: bitirdiği yan görevler epiloğa giriyor.
# (koşul, satır anahtarları) — koşul None ise sayfa her zaman gösterilir.
EPILOGUE = [
    (None,                                ["epi.1.1","epi.1.2","epi.1.3","epi.1.4"]),
    (None,                                ["epi.2.1","epi.2.2","epi.2.3","epi.2.4"]),
    (lambda f: f.get("sqpaid_fish"),      ["epi.fish.1","epi.fish.2"]),
    (lambda f: f.get("sqpaid_scroll"),    ["epi.scroll.1","epi.scroll.2"]),
    (lambda f: f.get("sqpaid_boar"),      ["epi.boar.1","epi.boar.2"]),
    (lambda f: f.get("sqpaid_witch") or f.get("sqpaid_hermit"),
                                          ["epi.quiet.1","epi.quiet.2"]),
    (lambda f: f.get("fire_crystal"),     ["epi.fire.1","epi.fire.2"]),
    (lambda f: f.get("light_crystal"),    ["epi.light.1","epi.light.2"]),
    (lambda f: f.get("fire_crystal") and f.get("light_crystal"),
                                          ["epi.four.1","epi.four.2"]),
    (None,                                ["epi.3.1","epi.3.2","epi.3.3","epi.3.4"]),
]

# Bitirilen yan görev sayısına göre unvan
ENDING_RANKS = [(14,"epi.rank_legend"),(10,"epi.rank_hero"),
                (5,"epi.rank_wanderer"),(0,"epi.rank_sealer")]


def epilogue_pages(flags):
    """Oyuncunun yaptıklarına göre gösterilecek epilog sayfaları."""
    return [satir for kosul,satir in EPILOGUE if kosul is None or kosul(flags)]


def ending_rank(flags)->str:
    n=sum(1 for sq in SIDE_QUESTS if flags.get("sqpaid_"+sq["id"]))
    # İsteğe bağlı kristaller de sayılır: dördünü de toplamak unvanı yükseltir
    n+=2*sum(1 for b in ("fire_crystal","light_crystal") if flags.get(b))
    for esik,anahtar in ENDING_RANKS:
        if n>=esik: return anahtar
    return ENDING_RANKS[-1][1]


# ─── Tile Tipleri ───────────────────────────────────────────────
class T:
    GRASS=0;DIRT=1;STONE=2;WATER=3;SAND=4;TREE=5;WALL=6;FLOOR=7
    DOOR=8;CHEST=9;STAIRS_UP=10;STAIRS_DN=11;CACTUS=12;SNOW=13
    ICE=14;SHADOW=15;DARK_TREE=16;RUINS_WALL=17;PORTAL=18
    SNOW_TREE=19;FARMLAND=20;WHEAT=21;RIVER=22;BRIDGE=23;FENCE=24
    # ROAD: köy yolu. Yollar eskiden STONE ile çiziliyordu ama STONE mağara
    # duvarı olduğu için yürünemiyordu — köyün ana yolları birer duvardı.
    # GATE: harita geçidi. Geçişin kendisi bu kare; kapı/mağara ağzı çiziliyor.
    ROAD=25;GATE=26
    STALL=27        # pazar tezgâhı: tenteli ahşap kepenk, yürünmez
    ASH=28;LAVA=29  # Köz Vadisi: yürünebilir kül, yürünemez lav
    # Doğal zemin çeşitleri. Haritaların çoğu tek bir karo tipiyle
    # kaplıydı (harabeler %100 FLOOR, kayalık geçit %99 DIRT) ve 16 kareye
    # kadar tek tip blok çıkıyordu: göz hiçbir şeye tutunamıyordu.
    PATH=30         # patika: sıkışmış toprak, çakıl, kenarda ot
    MEADOW=31       # yeşillik: çiçekli gür çayır
    HEDGE=32        # çalı çit — yürünmez, doğal çerçeve
    MOSS=33         # yosun tutmuş taş zemin
    RUBBLE=34       # döküntü: kırık taş ve toz
    GRAVEL=35       # çakıl yatağı
    PINE=36         # çam — yürünmez
    SHALLOW=37      # sığ su: geçilir
    CRACKED=38      # çatlamış kuru zemin

WALKABLE={T.GRASS,T.DIRT,T.SAND,T.SNOW,T.FARMLAND,T.WHEAT,
          T.FLOOR,T.DOOR,T.STAIRS_UP,T.STAIRS_DN,T.PORTAL,T.BRIDGE,T.ICE,
          T.ROAD,T.GATE,T.ASH,
          T.PATH,T.MEADOW,T.MOSS,T.RUBBLE,T.GRAVEL,T.SHALLOW,T.CRACKED}

# ─── Geçit ağzı üslupları ────────────────────────────────────────
# Geçitlerin hepsi aynı taş çerçeveydi: ormanın kenarında da, buz
# mağarasının ağzında da, kalenin kapısında da. Artık geçit gittiği yere
# benziyor; üslup haritada kare başına saklanıyor (m.gate_kind).
GATE_STYLES = ("cave","ruin","pass","arch","door","ice","ash")

# ─── Pixel Art ──────────────────────────────────────────────────
class PA:
    _c:Dict={}
    @staticmethod
    def tile(k,anim=0,style=None):
        ck=(k,anim//8 if k in(T.WATER,T.RIVER) else 0,style)
        if ck in PA._c: return PA._c[ck]
        s=pygame.Surface((TILE,TILE));rs=random.getstate();random.seed(hash(k)*997);Tp=TILE
        if k==T.GRASS:
            # Düz yeşile serpilmiş 10 açık kare yerine kademeli ton + ot
            # bıçakları: yan yana dizildiğinde ızgara görünmüyor.
            s.fill(G_D)
            for _ in range(7):
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(40,96,38),(bx,by,random.randint(4,7),random.randint(3,5)))
            for _ in range(9):
                bx,by=random.randint(1,Tp-2),random.randint(3,Tp-2)
                pygame.draw.line(s,G_L,(bx,by),(bx+random.choice((-1,1)),by-random.randint(2,4)),1)
        elif k==T.MEADOW:
            # Yeşillik: gür ot + ufak çiçekler. Köyün ve çayırın kenarları.
            s.fill((42,98,42))
            for _ in range(8):
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(50,116,46),(bx,by,random.randint(5,8),random.randint(4,6)))
            for _ in range(12):
                bx,by=random.randint(1,Tp-2),random.randint(4,Tp-1)
                pygame.draw.line(s,(70,142,62),(bx,by),(bx+random.choice((-1,0,1)),by-random.randint(3,6)),1)
            for _ in range(3):
                bx,by=random.randint(3,Tp-4),random.randint(4,Tp-5)
                c=random.choice(((232,224,120),(226,132,186),(176,196,236),(240,240,236)))
                pygame.draw.circle(s,c,(bx,by),2);pygame.draw.circle(s,(246,242,180),(bx,by),1)
        elif k==T.DIRT:
            s.fill(DT)
            for _ in range(6):
                bx,by=random.randint(0,Tp-6),random.randint(0,Tp-6)
                pygame.draw.ellipse(s,(112,76,38),(bx,by,random.randint(5,8),random.randint(4,6)))
            for _ in range(7):
                bx,by=random.randint(1,Tp-3),random.randint(1,Tp-3)
                pygame.draw.rect(s,DT_L,(bx,by,random.randint(2,3),2))
            for _ in range(4):
                bx,by=random.randint(2,Tp-3),random.randint(2,Tp-3)
                pygame.draw.circle(s,(146,132,110),(bx,by),1)
        elif k==T.PATH:
            # Patika: ayak izinin sıkıştırdığı açık toprak, kenarları otlu.
            s.fill((124,100,66))
            for _ in range(10):
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(140,116,78),(bx,by,random.randint(4,8),random.randint(3,5)))
            for _ in range(7):
                bx,by=random.randint(2,Tp-3),random.randint(2,Tp-3)
                pygame.draw.circle(s,(168,152,124),(bx,by),1)
            for _ in range(2):
                bx,by=random.randint(3,Tp-4),random.randint(3,Tp-4)
                pygame.draw.circle(s,(96,78,54),(bx,by),2)
            for ex in (0,Tp-2):
                for _ in range(4):
                    by=random.randint(1,Tp-4)
                    pygame.draw.line(s,(58,112,50),(ex+1,by+3),(ex+1,by),1)
        elif k==T.GRAVEL:
            s.fill((96,90,82))
            for _ in range(26):
                bx,by=random.randint(0,Tp-3),random.randint(0,Tp-3)
                c=random.choice(((120,114,104),(78,74,68),(138,130,118)))
                pygame.draw.circle(s,c,(bx,by),random.randint(1,2))
        elif k==T.CRACKED:
            s.fill((122,104,82))
            for _ in range(5):
                bx,by=random.randint(0,Tp-7),random.randint(0,Tp-7)
                pygame.draw.ellipse(s,(136,118,92),(bx,by,random.randint(6,9),random.randint(5,7)))
            for _ in range(3):
                bx,by=random.randint(0,Tp-6),random.randint(0,Tp-6)
                pygame.draw.ellipse(s,(106,90,70),(bx,by,random.randint(4,7),random.randint(3,5)))
            for _ in range(4):
                x1,y1=random.randint(0,Tp-1),random.randint(0,Tp-1);pts=[(x1,y1)]
                for _ in range(3):
                    x1=max(0,min(Tp-1,x1+random.randint(-7,7)))
                    y1=max(0,min(Tp-1,y1+random.randint(-7,7)))
                    pts.append((x1,y1))
                pygame.draw.lines(s,(84,68,52),False,pts,1)
                pygame.draw.line(s,(152,134,106),(pts[0][0],pts[0][1]-1),
                                 (pts[1][0],pts[1][1]-1),1)
            for _ in range(5):                     # kuru toz tanecikleri
                bx,by=random.randint(1,Tp-2),random.randint(1,Tp-2)
                pygame.draw.circle(s,(168,150,120),(bx,by),1)
        elif k==T.MOSS:
            s.fill((62,66,58))
            for r in range(2):
                for c in range(2):
                    pygame.draw.rect(s,(78,82,72),(c*16+1,r*16+1,13,13))
                    pygame.draw.rect(s,(48,52,44),(c*16+1,r*16+1,13,13),1)
            for _ in range(9):
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(66,106,58),(bx,by,random.randint(4,7),random.randint(3,5)))
            for _ in range(4):
                bx,by=random.randint(1,Tp-2),random.randint(3,Tp-2)
                pygame.draw.line(s,(88,140,72),(bx,by),(bx,by-2),1)
        elif k==T.RUBBLE:
            s.fill((74,70,66))
            for _ in range(13):
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                w2,h2=random.randint(3,6),random.randint(2,4)
                pygame.draw.rect(s,(100,96,90),(bx,by,w2,h2))
                pygame.draw.rect(s,(56,52,48),(bx,by,w2,h2),1)
            for _ in range(6):
                bx,by=random.randint(1,Tp-2),random.randint(1,Tp-2)
                pygame.draw.circle(s,(118,112,104),(bx,by),1)
        elif k==T.SHALLOW:
            # Sığ su: geçilir. Dibi görünüyor, üstünde kıpırtı var.
            ph=(anim%48)/48.0
            s.fill((62,116,146))
            for _ in range(5):                     # derinleşen yerler
                bx,by=random.randint(0,Tp-8),random.randint(0,Tp-6)
                pygame.draw.ellipse(s,(48,98,128),(bx,by,random.randint(6,10),random.randint(4,6)))
            for _ in range(7):                     # dipteki çakıl
                bx,by=random.randint(0,Tp-5),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(92,86,70),(bx,by,random.randint(4,7),random.randint(3,5)))
            for _ in range(4):
                bx,by=random.randint(1,Tp-2),random.randint(1,Tp-2)
                pygame.draw.circle(s,(126,116,96),(bx,by),1)
            for yy in range(2,Tp,7):               # yüzeydeki kıpırtı
                off=int(3*math.sin(2*math.pi*(ph+yy/float(Tp))))
                pygame.draw.line(s,(150,200,222),(2+off,yy),(Tp-4+off,yy),1)
                pygame.draw.line(s,(96,160,190),(2+off,yy+1),(Tp-4+off,yy+1),1)
        elif k==T.HEDGE:
            # Çalı çit: taş duvar yerine doğal çerçeve.
            s.fill(G_D)
            for cxx,cyy,r in ((8,20,9),(22,20,9),(15,13,9),(5,12,6),(26,13,6)):
                pygame.draw.circle(s,(26,66,30),(cxx,cyy),r)
            for cxx,cyy,r in ((9,17,6),(21,18,6),(15,11,6),(16,21,5)):
                pygame.draw.circle(s,(44,100,44),(cxx,cyy),r)
            for _ in range(7):
                bx,by=random.randint(3,Tp-4),random.randint(4,Tp-6)
                pygame.draw.circle(s,(62,128,56),(bx,by),2)
            for _ in range(3):
                bx,by=random.randint(4,Tp-5),random.randint(6,Tp-8)
                pygame.draw.circle(s,(188,66,58),(bx,by),1)
        elif k==T.PINE:
            # Çam: dar ve dik; kayalık geçide ve soğuk bölgelere ait.
            s.fill((46,54,44))
            pygame.draw.rect(s,(68,48,30),(14,22,4,10))
            for i,(wd,yy) in enumerate(((13,20),(11,15),(8,10),(5,5))):
                pygame.draw.polygon(s,(18,56,34) if i%2==0 else (24,70,42),
                                    [(16,yy-5),(16-wd,yy+4),(16+wd,yy+4)])
            pygame.draw.polygon(s,(34,88,52),[(16,2),(13,8),(19,8)])
        elif k==T.STONE:
            s.fill(ST)
            for r in range(2):
                for c in range(2):
                    ox=c*16+(r*8%16);oy=r*16
                    pygame.draw.rect(s,ST_L,(ox+1,oy+1,13,13));pygame.draw.rect(s,ST,(ox+1,oy+1,13,13),1)
        elif k==T.ASH:
            s.fill((62,54,52))
            for _ in range(14):
                bx,by=random.randint(0,Tp-3),random.randint(0,Tp-3)
                pygame.draw.rect(s,(78,68,64),(bx,by,2,2))
            for _ in range(4):                 # sönmek üzere közler
                bx,by=random.randint(1,Tp-3),random.randint(1,Tp-3)
                pygame.draw.rect(s,(150,70,36),(bx,by,2,2))
        elif k==T.LAVA:
            ph=(anim%40)/40.0
            s.fill((122,32,12))
            for yy in range(0,Tp,4):
                g=int(40*math.sin(2*math.pi*(ph+yy/float(Tp))))
                pygame.draw.rect(s,(min(255,210+g),min(255,96+g),24),(0,yy,Tp,3))
            for _ in range(5):
                bx,by=random.randint(0,Tp-3),random.randint(0,Tp-3)
                pygame.draw.rect(s,(255,220,140),(bx,by,2,2))
        elif k==T.STALL:
            s.fill(DT)
            for i in range(0,Tp,8):        # çizgili tente
                pygame.draw.rect(s,(188,62,56) if (i//8)%2==0 else (238,228,208),(i,0,8,13))
            pygame.draw.rect(s,(122,42,38),(0,12,Tp,3))
            pygame.draw.rect(s,(86,62,40),(1,15,3,Tp-20))      # direkler
            pygame.draw.rect(s,(86,62,40),(Tp-4,15,3,Tp-20))
            pygame.draw.rect(s,(112,84,54),(0,Tp-6,Tp,6))      # tezgâh tahtası
            for i in range(0,Tp,7): pygame.draw.line(s,(78,56,34),(i,Tp-6),(i,Tp-1),1)
        elif k==T.ROAD:
            s.fill((96,92,86))
            for r in range(4):
                for c in range(4):
                    ox=c*8+(r%2)*4;oy=r*8
                    pygame.draw.rect(s,(126,122,114),(ox+1,oy+1,6,6))
                    pygame.draw.rect(s,(74,70,66),(ox+1,oy+1,6,6),1)
        elif k==T.GATE:
            PA._gate_tile(s,style or "cave",Tp)
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
            # Kırışıklar kesintili ve kaydırmalı: boydan boya çizgi olursa
            # kum değil ahşap gibi görünüyor.
            s.fill(SD)
            for _ in range(9):
                bx,by=random.randint(0,Tp-9),random.randint(1,Tp-2)
                w2=random.randint(5,10)
                pygame.draw.line(s,(202,178,126),(bx,by),(bx+w2,by+random.choice((-1,0,1))),1)
            for _ in range(5):
                bx,by=random.randint(0,Tp-7),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,(196,170,116),(bx,by,random.randint(5,8),random.randint(3,4)))
            for _ in range(6):
                bx,by=random.randint(1,Tp-3),random.randint(1,Tp-3)
                pygame.draw.circle(s,(216,198,152),(bx,by),1)
            for _ in range(2):
                bx,by=random.randint(2,Tp-4),random.randint(2,Tp-4)
                pygame.draw.circle(s,(160,136,86),(bx,by),1)
        elif k==T.SNOW:
            s.fill(SN)
            for _ in range(5):                     # rüzgârın savurduğu yığıntı
                bx,by=random.randint(0,Tp-8),random.randint(0,Tp-5)
                pygame.draw.ellipse(s,SN_L,(bx,by,random.randint(6,10),random.randint(3,5)))
            for _ in range(8):
                bx,by=random.randint(2,Tp-3),random.randint(2,Tp-3)
                pygame.draw.circle(s,WH,(bx,by),1)
            for _ in range(2):
                bx,by=random.randint(2,Tp-4),random.randint(2,Tp-4)
                pygame.draw.circle(s,(158,180,202),(bx,by),1)
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
            # Han ve ev kapısı: taş söve, iki kanatlı tahta, demir menteşe.
            s.fill(FL)
            pygame.draw.rect(s,(92,86,76),(5,0,22,32))         # söve
            pygame.draw.rect(s,(120,112,100),(5,0,22,3))
            pygame.draw.rect(s,(58,40,24),(8,3,16,29))
            for i in range(9,24,4):                            # tahtalar
                pygame.draw.rect(s,(142,98,50),(i,4,3,27))
                pygame.draw.line(s,(104,68,34),(i+2,4),(i+2,30),1)
            for yy in (9,22):                                  # menteşeler
                pygame.draw.rect(s,(62,62,68),(8,yy,16,3))
                pygame.draw.line(s,(112,112,120),(8,yy),(23,yy),1)
            pygame.draw.circle(s,(198,164,72),(20,17),3,1)      # tokmak
            pygame.draw.circle(s,(230,200,110),(20,17),1)
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

    # ── Geçit ağızları ───────────────────────────────────────────
    # Her geçit gittiği yere benziyor: ormanın kenarında dal kemeri, dağ
    # geçidinde kaya yarığı, buz mağarasında buz sütunu, kalede ahşap kapı.
    # Kare dört kenarından da çerçeveli çiziliyor; böylece geçit ister
    # dikey ister yatay dizilsin üç kare tek bir ağız gibi okunuyor.
    @staticmethod
    def _gate_cerceve(s,Tp,tas,derz,kalin=3):
        """Dört kenara taş/ahşap çerçeve + derzler."""
        pygame.draw.rect(s,tas,(0,0,Tp,kalin));pygame.draw.rect(s,tas,(0,Tp-kalin,Tp,kalin))
        pygame.draw.rect(s,tas,(0,0,kalin,Tp));pygame.draw.rect(s,tas,(Tp-kalin,0,kalin,Tp))
        for i in range(0,Tp,8):
            pygame.draw.line(s,derz,(i,0),(i,kalin-1),1)
            pygame.draw.line(s,derz,(i,Tp-kalin),(i,Tp-1),1)
            pygame.draw.line(s,derz,(0,i),(kalin-1,i),1)
            pygame.draw.line(s,derz,(Tp-kalin,i),(Tp-1,i),1)

    @staticmethod
    def _gate_tile(s,style,Tp):
        if style=="door":
            # Han / kale kapısı: iki kanatlı ahşap, demir kuşaklı, taş söveli
            s.fill((58,42,28))
            for i in range(4,Tp-3,5):              # tahta damarları
                pygame.draw.rect(s,(126,86,46),(i,4,4,Tp-8))
                pygame.draw.line(s,(96,62,32),(i+3,4),(i+3,Tp-5),1)
            pygame.draw.rect(s,(74,70,66),(0,0,Tp,4))          # taş lento
            pygame.draw.rect(s,(96,92,86),(0,0,Tp,2))
            for yy in (9,Tp-12):                   # demir kuşaklar
                pygame.draw.rect(s,(58,58,64),(1,yy,Tp-2,3))
                pygame.draw.line(s,(104,104,112),(1,yy),(Tp-2,yy),1)
                for bx in range(3,Tp-2,7): pygame.draw.circle(s,(142,142,150),(bx,yy+1),1)
            pygame.draw.line(s,(42,28,16),(Tp//2,4),(Tp//2,Tp-1),2)   # kanat aralığı
            pygame.draw.circle(s,(190,158,70),(Tp//2-5,Tp//2+2),3,1)  # halka tokmak
            pygame.draw.circle(s,(190,158,70),(Tp//2+5,Tp//2+2),3,1)
            PA._gate_cerceve(s,Tp,(74,70,66),(52,48,44),2)
        elif style=="arch":
            # Orman/çayır kemeri: eğilmiş dallar, sarmaşık, dipte ot
            s.fill((22,44,24))
            for i in range(3,Tp,6):                # ağaç gövdesi arası derinlik
                pygame.draw.line(s,(16,34,18),(i,5),(i,Tp-6),1)
            pygame.draw.rect(s,(74,52,30),(0,0,Tp,5))          # üstteki dal
            pygame.draw.rect(s,(100,72,42),(0,0,Tp,2))
            pygame.draw.rect(s,(74,52,30),(0,0,4,Tp))          # yan gövdeler
            pygame.draw.rect(s,(74,52,30),(Tp-4,0,4,Tp))
            pygame.draw.line(s,(100,72,42),(1,0),(1,Tp-1),1)
            pygame.draw.line(s,(100,72,42),(Tp-2,0),(Tp-2,Tp-1),1)
            for lx,ly in ((3,6),(9,3),(16,2),(23,3),(29,6),(2,14),(29,15),(3,24),(28,23)):
                pygame.draw.ellipse(s,(32,92,38),(lx-3,ly-2,7,5))
                pygame.draw.ellipse(s,(52,124,50),(lx-2,ly-1,4,3))
            for gx in range(2,Tp-1,5):             # dipteki ot
                pygame.draw.line(s,(46,106,44),(gx,Tp-1),(gx-1,Tp-6),1)
                pygame.draw.line(s,(62,132,58),(gx,Tp-1),(gx+1,Tp-5),1)
        elif style=="pass":
            # Dağ geçidi: iki yanda yüksek kaya, ortada aydınlık yarık
            s.fill((150,154,166))                  # uzaktaki aydınlık yarık
            for yy in range(0,Tp,4):
                g=138+(yy*2)//3
                pygame.draw.rect(s,(min(255,g),min(255,g+5),min(255,g+14)),(3,yy,Tp-6,4))
            for (x0,yon) in ((0,1),(Tp-4,-1)):     # ince kaya yüzleri
                for yy in range(0,Tp,5):
                    w=3+(yy//10)%2
                    x=x0 if yon>0 else Tp-w
                    pygame.draw.rect(s,(78,76,84),(x,yy,w,5))
                    pygame.draw.rect(s,(106,104,114),(x,yy,w,2))
                    pygame.draw.line(s,(56,54,60),(x,yy+4),(x+w,yy+4),1)
            for _ in range(5):                     # dipte dökülmüş taşlar
                bx,by=random.randint(5,Tp-7),random.randint(Tp-8,Tp-3)
                pygame.draw.circle(s,(104,102,110),(bx,by),2)
                pygame.draw.circle(s,(140,138,148),(bx-1,by-1),1)
            pygame.draw.rect(s,(146,150,160),(0,0,Tp,3))       # tepede kar
            pygame.draw.rect(s,(214,222,234),(0,0,Tp,1))
            pygame.draw.rect(s,(120,118,128),(0,Tp-2,Tp,2))
        elif style=="ice":
            # Buz mağarası ağzı: donmuş sütunlar, sarkıt buzlar
            s.fill((30,58,82))
            for i in range(2,Tp,6):
                pygame.draw.line(s,(42,78,108),(i,4),(i,Tp-4),1)
            PA._gate_cerceve(s,Tp,(126,176,206),(88,140,178),3)
            pygame.draw.rect(s,(188,226,244),(0,0,Tp,1))
            for ix in range(3,Tp-2,6):             # sarkıt
                h=random.randint(5,11)
                pygame.draw.polygon(s,(168,214,238),[(ix,3),(ix+3,3),(ix+1,3+h)])
                pygame.draw.line(s,(226,246,255),(ix+1,3),(ix+1,3+h-2),1)
            for ix in range(5,Tp-2,7):             # dipte yükselen buz
                h=random.randint(4,8)
                pygame.draw.polygon(s,(140,194,224),[(ix,Tp-3),(ix+3,Tp-3),(ix+1,Tp-3-h)])
        elif style=="ash":
            # Köz Vadisi ağzı: isli bazalt, dipte sönmeyen köz
            s.fill((26,20,18))
            for i in range(3,Tp,6):
                pygame.draw.line(s,(38,28,24),(i,4),(i,Tp-4),1)
            PA._gate_cerceve(s,Tp,(56,48,46),(34,28,26),3)
            for _ in range(7):                     # çerçevede köz damarları
                bx=random.randint(1,Tp-2)
                pygame.draw.line(s,(188,76,32),(bx,Tp-3),(bx,Tp-1),1)
            for _ in range(5):
                bx,by=random.randint(4,Tp-5),random.randint(Tp-10,Tp-4)
                pygame.draw.circle(s,(226,110,40),(bx,by),1)
            for _ in range(3):                     # duman
                bx,by=random.randint(5,Tp-6),random.randint(5,14)
                pygame.draw.circle(s,(62,56,54),(bx,by),2)
        elif style=="ruin":
            # Yıkık taş kemer: kırık söve, kilit taşı, sarmaşık
            s.fill((22,19,17))
            for i in range(4,Tp,7):
                pygame.draw.line(s,(32,28,25),(i,3),(i,Tp-4),1)
            PA._gate_cerceve(s,Tp,(88,78,66),(58,50,42),3)
            pygame.draw.rect(s,(112,100,84),(Tp//2-4,0,8,4))   # kilit taşı
            pygame.draw.line(s,(62,54,46),(Tp//2,0),(Tp//2,3),1)
            for _ in range(5):                     # çatlaklar
                bx=random.randint(2,Tp-3)
                pygame.draw.line(s,(50,44,38),(bx,0),(bx+random.randint(-2,2),3),1)
            for vy in (7,15,23):                   # sarmaşık
                pygame.draw.line(s,(44,86,44),(2,vy),(5,vy+4),1)
                pygame.draw.ellipse(s,(56,110,52),(4,vy+3,4,3))
                pygame.draw.line(s,(44,86,44),(Tp-3,vy+3),(Tp-6,vy+7),1)
                pygame.draw.ellipse(s,(56,110,52),(Tp-8,vy+6,4,3))
        else:   # "cave" — mağara ağzı: kaba taş, dipsiz karanlık
            s.fill((20,17,16))
            for i in range(4,Tp,7):
                pygame.draw.line(s,(30,26,24),(i,3),(i,Tp-4),1)
            PA._gate_cerceve(s,Tp,(96,88,78),(66,60,53),3)
            for ix in range(4,Tp-2,6):             # üstte kaya dişleri
                h=random.randint(3,7)
                pygame.draw.polygon(s,(84,76,68),[(ix,3),(ix+4,3),(ix+2,3+h)])
            for ix in range(6,Tp-2,7):
                h=random.randint(2,5)
                pygame.draw.polygon(s,(84,76,68),[(ix,Tp-3),(ix+4,Tp-3),(ix+2,Tp-3-h)])

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
        s=PA._finish(PA._enemy_raw(kind,af),shadow=(kind not in BIG_SPRITES))
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
        elif kind=="bat":
            # Yarasa: küçük, hızlı, kanatları kare kare çırpıyor
            kanat=PA._bob(af,5.0)
            for yon in (-1,1):
                pygame.draw.polygon(s,(62,44,78),
                    [(16,15+bob),(16+yon*15,10+bob-kanat),(16+yon*13,19+bob+kanat//2)])
                pygame.draw.polygon(s,(92,70,112),
                    [(16,16+bob),(16+yon*10,13+bob-kanat//2),(16+yon*9,19+bob)])
            pygame.draw.ellipse(s,(74,54,90),(11,12+bob,10,12))
            pygame.draw.ellipse(s,(96,74,116),(12,13+bob,7,6))
            pygame.draw.polygon(s,(74,54,90),[(12,12+bob),(10,5+bob),(15,11+bob)])
            pygame.draw.polygon(s,(74,54,90),[(20,12+bob),(22,5+bob),(17,11+bob)])
            pygame.draw.circle(s,(255,120,90),(14,16+bob),2)
            pygame.draw.circle(s,(255,120,90),(19,16+bob),2)
            pygame.draw.rect(s,(240,236,230),(15,20+bob,1,2))
            pygame.draw.rect(s,(240,236,230),(17,20+bob,1,2))
        elif kind=="spider":
            # Dev örümcek: sekiz bacak, şiş karın, sekiz göz
            for i,(lx,ly) in enumerate(((6,19),(4,22),(5,26),(8,28))):
                bk=step if i%2 else -step
                pygame.draw.lines(s,(44,34,44),False,
                                  [(13,21+bob),(lx,ly+bob+bk),(lx-3,ly+5+bob)],2)
                pygame.draw.lines(s,(44,34,44),False,
                                  [(19,21+bob),(32-lx,ly+bob-bk),(35-lx,ly+5+bob)],2)
            pygame.draw.ellipse(s,(58,44,56),(9,18+bob,15,13))     # karın
            pygame.draw.ellipse(s,(84,64,80),(11,19+bob,10,7))
            for mx,my in ((13,22),(18,24),(16,28)):
                pygame.draw.circle(s,(214,200,120),(mx,my+bob),2)
            pygame.draw.ellipse(s,(48,36,48),(11,10+bob,11,10))    # baş göğüs
            for ex,ey,r in ((13,13,2),(19,13,2),(14,17,1),(18,17,1)):
                pygame.draw.circle(s,(230,70,70),(ex,ey+bob),r)
            pygame.draw.line(s,(40,30,40),(12,19+bob),(9,22+bob),2)
            pygame.draw.line(s,(40,30,40),(21,19+bob),(24,22+bob),2)
        elif kind=="bandit":
            # Haydut: kukuletalı insan, elinde hançer
            pygame.draw.rect(s,(58,52,46),(11,26+bob,4,5+step//2))
            pygame.draw.rect(s,(58,52,46),(18,26+bob,4,5-step//2))
            pygame.draw.polygon(s,(94,74,52),[(9,16+bob),(24,16+bob),(26,28+bob),(7,28+bob)])
            pygame.draw.rect(s,(126,100,70),(12,18+bob,9,7))
            pygame.draw.rect(s,(72,56,38),(8,22+bob,18,3))          # kemer
            pygame.draw.rect(s,(206,170,80),(15,21+bob,4,4))        # toka
            pygame.draw.polygon(s,(66,58,50),[(10,14+bob),(23,14+bob),(21,4+bob),(12,4+bob)])
            pygame.draw.ellipse(s,(196,160,122),(12,8+bob,10,9))    # yüz
            pygame.draw.polygon(s,(52,46,40),[(10,12+bob),(23,12+bob),(21,3+bob),(12,3+bob)])
            pygame.draw.rect(s,(40,36,34),(12,10+bob,10,3))         # gözleri gölgede
            pygame.draw.circle(s,(250,230,120),(15,11+bob),1)
            pygame.draw.circle(s,(250,230,120),(19,11+bob),1)
            pygame.draw.line(s,(78,62,44),(25,20+bob),(25,24+bob),2) # hançer
            pygame.draw.polygon(s,(214,218,226),[(24,20+bob),(27,20+bob),(25,11+bob)])
        elif kind=="wraith":
            # Hayalet: ayağı yok, paçavra kefen, boşlukta süzülüyor
            sv=PA._bob(af,3.0)
            aa=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*55)+30
            asurf=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            pygame.draw.circle(asurf,(150,170,220,aa),(16,16),14);s.blit(asurf,(0,0))
            etek=[(7,16+sv),(25,16+sv)]
            for i,ox in enumerate((25,21,17,13,9,5)):
                etek.append((ox,(30 if i%2 else 26)+sv))
            pygame.draw.polygon(s,(74,84,112),etek)
            pygame.draw.polygon(s,(104,116,148),
                                [(10,16+sv),(22,16+sv),(20,25+sv),(12,25+sv)])
            pygame.draw.ellipse(s,(88,98,128),(9,4+sv,14,14))        # kukuleta
            pygame.draw.ellipse(s,(18,20,30),(11,7+sv,10,10))        # içi karanlık
            gl=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*120)+110
            pygame.draw.circle(s,(gl,gl//2,255),(13,12+sv),2)
            pygame.draw.circle(s,(gl,gl//2,255),(19,12+sv),2)
            pygame.draw.line(s,(104,116,148),(6,14+sv),(2,20+sv),2)  # kol gibi paçavra
            pygame.draw.line(s,(104,116,148),(26,14+sv),(30,20+sv),2)
        elif kind=="treant":
            # Ağaç kök: gövde beden, dal kollar, yapraklı taç
            pygame.draw.polygon(s,(74,54,34),[(10,27+bob),(6,31+bob),(14,31+bob)])
            pygame.draw.polygon(s,(74,54,34),[(21,27+bob),(17,31+bob),(26,31+bob)])
            pygame.draw.rect(s,(96,70,42),(10,14+bob,12,14))
            pygame.draw.rect(s,(118,88,54),(12,15+bob,5,12))
            for yy in (17,21,25):
                pygame.draw.line(s,(68,48,30),(11,yy+bob),(21,yy+bob),1)
            pygame.draw.lines(s,(86,62,38),False,
                              [(10,18+bob),(4,14+bob-step),(1,8+bob)],2)
            pygame.draw.lines(s,(86,62,38),False,
                              [(22,18+bob),(28,14+bob+step),(31,8+bob)],2)
            for cxx,cyy,r in ((16,7,8),(8,9,6),(24,9,6),(16,3,5)):
                pygame.draw.circle(s,(30,80,38),(cxx,cyy+bob),r)
            for cxx,cyy,r in ((14,6,5),(22,8,4),(9,8,3)):
                pygame.draw.circle(s,(52,118,54),(cxx,cyy+bob),r)
            pygame.draw.circle(s,(230,200,70),(13,18+bob),2)         # gözler
            pygame.draw.circle(s,(230,200,70),(19,18+bob),2)
            pygame.draw.circle(s,BK,(13,18+bob),1);pygame.draw.circle(s,BK,(19,18+bob),1)
        elif kind=="lava_imp":
            # Köz cini: küçük, boynuzlu, içi yanıyor
            par=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*70)+120
            asurf=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            pygame.draw.circle(asurf,(240,90,20,70),(16,18),12);s.blit(asurf,(0,0))
            pygame.draw.rect(s,(104,34,24),(11,26+bob,4,5+step//2))
            pygame.draw.rect(s,(104,34,24),(18,26+bob,4,5-step//2))
            pygame.draw.ellipse(s,(150,48,28),(9,15+bob,15,13))
            pygame.draw.ellipse(s,(196,74,36),(11,16+bob,10,7))
            for fx,fy in ((13,22),(18,20),(16,25)):
                pygame.draw.circle(s,(par,110,30),(fx,fy+bob),2)
            pygame.draw.ellipse(s,(166,56,30),(10,5+bob,13,12))      # kafa
            pygame.draw.polygon(s,(74,26,18),[(10,7+bob),(6,bob),(13,5+bob)])
            pygame.draw.polygon(s,(74,26,18),[(22,7+bob),(26,bob),(19,5+bob)])
            pygame.draw.circle(s,(255,230,120),(14,10+bob),2)
            pygame.draw.circle(s,(255,230,120),(19,10+bob),2)
            pygame.draw.circle(s,BK,(14,10+bob),1);pygame.draw.circle(s,BK,(19,10+bob),1)
            pygame.draw.line(s,(255,180,60),(13,14+bob),(20,14+bob),1)
            pygame.draw.line(s,(150,48,28),(23,20+bob),(29,16+bob-step),2)  # kuyruk
            pygame.draw.circle(s,(par,120,40),(30,15+bob-step),2)
        elif kind=="ember_titan":
            # Köz Devi: erimiş kayadan bir dev. Malachar gibi 2x2 çiziliyor.
            sc=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA);b2=PA._bob(af,2.5)
            par=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*90)+120
            hs=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA)
            pygame.draw.circle(hs,(250,110,30,60),(32,34),28);sc.blit(hs,(0,0))
            pygame.draw.rect(sc,(54,38,34),(10,46+b2,14,16))     # bacaklar
            pygame.draw.rect(sc,(54,38,34),(40,46+b2,14,16))
            pygame.draw.rect(sc,(68,48,42),(4,22+b2,12,26))      # kollar
            pygame.draw.rect(sc,(68,48,42),(48,22+b2,12,26))
            pygame.draw.rect(sc,(72,52,46),(12,18+b2,40,32))     # gövde
            pygame.draw.rect(sc,(94,66,56),(16,22+b2,32,20))
            for ly in range(24,46,6):                            # lav damarları
                pygame.draw.line(sc,(par,70,24),(14,ly+b2),(50,ly+b2+2),2)
                pygame.draw.line(sc,(255,190,90),(14,ly+b2),(28,ly+b2+1),1)
            pygame.draw.rect(sc,(62,44,38),(18,4+b2,28,16))      # kafa
            pygame.draw.polygon(sc,(84,58,48),[(18,6+b2),(10,b2-4),(22,4+b2)])
            pygame.draw.polygon(sc,(84,58,48),[(46,6+b2),(54,b2-4),(42,4+b2)])
            pygame.draw.circle(sc,(par,90,20),(26,12+b2),5)
            pygame.draw.circle(sc,(par,90,20),(38,12+b2),5)
            pygame.draw.circle(sc,(255,230,150),(26,12+b2),2)
            pygame.draw.circle(sc,(255,230,150),(38,12+b2),2)
            for mx in range(20,46,5):                            # ağızdaki köz
                pygame.draw.rect(sc,(240,140,50),(mx,18+b2,3,2))
            return sc
        elif kind=="page_warden":
            # Sayfa Muhafızı: kitaplardan ve mürekkepten örülmüş bir bekçi
            sc=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA);b3=PA._bob(af,3.0)
            par=int(abs(math.sin(af/PA.ANIM_FRAMES*math.tau))*80)+130
            hs=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA)
            pygame.draw.circle(hs,(250,230,150,55),(32,30),28);sc.blit(hs,(0,0))
            # Etrafında dönen sayfalar
            for i in range(6):
                ang=af/PA.ANIM_FRAMES*math.tau+i*1.047
                sx2=int(32+26*math.cos(ang));sy2=int(32+14*math.sin(ang))
                pygame.draw.rect(sc,(238,232,214),(sx2-3,sy2-4,7,8))
                pygame.draw.rect(sc,(188,176,150),(sx2-3,sy2-4,7,8),1)
            pygame.draw.polygon(sc,(44,36,66),                   # cüppe
                                [(14,24+b3),(50,24+b3),(56,60+b3),(8,60+b3)])
            pygame.draw.polygon(sc,(68,56,100),[(20,28+b3),(44,28+b3),(48,56+b3),(16,56+b3)])
            for ly in range(32,56,7):                            # satır satır yazı
                pygame.draw.line(sc,(206,196,170),(20,ly+b3),(44,ly+b3),1)
            pygame.draw.rect(sc,(120,96,54),(4,30+b3,12,16))     # koltuk altında kitap
            pygame.draw.rect(sc,(226,220,200),(6,32+b3,8,12))
            pygame.draw.ellipse(sc,(52,44,78),(18,4+b3,28,24))   # kukuleta
            pygame.draw.ellipse(sc,(16,14,24),(22,8+b3,20,18))
            pygame.draw.circle(sc,(par,par-30,110),(28,18+b3),4)
            pygame.draw.circle(sc,(par,par-30,110),(38,18+b3),4)
            pygame.draw.circle(sc,(255,250,220),(28,18+b3),2)
            pygame.draw.circle(sc,(255,250,220),(38,18+b3),2)
            pygame.draw.rect(sc,(188,160,80),(20,2+b3,24,5))     # altın bant
            return sc
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
        elif kind=="web":
            pygame.draw.circle(s,(226,226,236),(9,9),7,1)
            pygame.draw.circle(s,(206,206,220),(9,9),4,1)
            for i in range(6):
                ang=i*1.05+frame*0.08
                pygame.draw.line(s,(236,236,246),(9,9),
                                 (int(9+7*math.cos(ang)),int(9+7*math.sin(ang))),1)
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
        elif kind=="fern":
            for ang,ln in ((-0.9,11),(-0.3,13),(0.3,13),(0.9,11)):
                ex=16+int(math.sin(ang)*ln);ey=24-int(math.cos(ang)*ln)
                pygame.draw.line(s,(38,96,44),(16,25),(ex,ey),2)
                for t in (0.45,0.7,0.9):
                    mx=16+int((ex-16)*t);my=25+int((ey-25)*t)
                    pygame.draw.circle(s,(58,132,58),(mx,my),2)
        elif kind=="pebbles":
            for px,py,r in ((11,22,2),(16,24,1),(20,21,2),(14,19,1),(22,24,1)):
                pygame.draw.circle(s,(118,112,102),(px,py),r)
                pygame.draw.circle(s,(152,146,134),(px,py-1),1)
        elif kind=="ember":
            pygame.draw.ellipse(s,(52,40,36),(9,20,14,7))
            for px,py in ((12,23),(16,22),(20,24),(14,21)):
                pygame.draw.circle(s,(218,96,34),(px,py),2)
                pygame.draw.circle(s,(255,196,110),(px,py),1)
            pygame.draw.circle(s,(90,78,74),(17,16),2)
        elif kind=="obsidian":
            pygame.draw.polygon(s,(28,22,30),((16,9),(23,22),(16,26),(10,22)))
            pygame.draw.polygon(s,(62,48,66),((16,12),(20,21),(16,24),(13,21)))
            pygame.draw.line(s,(140,110,150),(16,13),(16,22),1)
        elif kind=="icespike":
            pygame.draw.polygon(s,(150,200,230),((16,6),(21,25),(11,25)))
            pygame.draw.polygon(s,(210,240,255),((16,9),(18,24),(15,24)))
            pygame.draw.polygon(s,(130,180,214),((23,16),(26,25),(20,25)))
        elif kind=="stalagmite":
            pygame.draw.polygon(s,(92,88,82),((15,8),(21,26),(9,26)))
            pygame.draw.polygon(s,(124,120,112),((15,12),(18,25),(13,25)))
        elif kind=="reed":
            for rx,h in ((11,14),(16,18),(21,13),(25,16)):
                pygame.draw.line(s,(72,112,58),(rx,26),(rx+1,26-h),1)
                pygame.draw.ellipse(s,(128,96,52),(rx-1,26-h-4,3,5))
        elif kind=="lilypad":
            pygame.draw.circle(s,(44,110,56),(14,20),6)
            pygame.draw.circle(s,(62,138,70),(14,19),4)
            pygame.draw.circle(s,(44,110,56),(23,24),4)
            pygame.draw.circle(s,(232,228,240),(14,19),2)
        elif kind=="skull":
            pygame.draw.ellipse(s,(216,210,196),(11,16,11,9))
            pygame.draw.rect(s,(216,210,196),(14,23,5,3))
            pygame.draw.circle(s,(40,36,34),(14,20),2);pygame.draw.circle(s,(40,36,34),(19,20),2)
        elif kind=="barrel":
            pygame.draw.ellipse(s,(104,70,38),(10,12,13,17))
            pygame.draw.ellipse(s,(138,96,52),(11,13,11,15))
            for yy in (16,22): pygame.draw.line(s,(68,64,58),(11,yy),(22,yy),2)
            pygame.draw.ellipse(s,(150,110,62),(11,11,11,5))
        elif kind=="crate":
            pygame.draw.rect(s,(118,82,44),(9,14,16,14))
            pygame.draw.rect(s,(84,56,28),(9,14,16,14),2)
            pygame.draw.line(s,(146,106,58),(9,14),(24,27),1)
            pygame.draw.line(s,(146,106,58),(24,14),(9,27),1)
        elif kind=="pot":
            pygame.draw.ellipse(s,(132,86,62),(11,15,12,13))
            pygame.draw.ellipse(s,(164,112,80),(12,16,9,9))
            pygame.draw.rect(s,(104,66,46),(13,13,8,3))
        elif kind=="vine":
            pygame.draw.lines(s,(48,96,46),False,((8,6),(12,13),(9,20),(13,27)),2)
            for vy in (11,18,25): pygame.draw.ellipse(s,(66,128,56),(11,vy,5,4))
        elif kind=="cobweb":
            for ang in range(0,5):
                ex=4+ang*3;ey=4+(4-ang)*3
                pygame.draw.line(s,(188,188,200),(2,2),(ex+8,ey+8),1)
            pygame.draw.arc(s,(188,188,200),(0,0,22,22),3.5,5.0,1)
            pygame.draw.arc(s,(188,188,200),(0,0,32,32),3.5,5.0,1)
        PA._c[key]=s;return s

    # ── Oyun içi logo: Karanlık Taç ──────────────────────────────
    # Masaüstü/görev çubuğu ikonundan ayrı: bu amblem oyunun içinde, açılış
    # animasyonunda ve başlık ekranında kullanılıyor. Her şey gibi çalışma
    # anında çiziliyor, yanında bir görsel dosyası yok.
    _logo_c:Dict={}

    @staticmethod
    def logo(catlak=1.0,sade=False):
        """Taç amblemi. catlak: 0 = sağlam, 1 = tam çatlak (animasyon için).
        sade=True küçük boyda okunsun diye ayrıntıları atar (ikon)."""
        ck=(round(catlak,2),sade)
        if ck in PA._logo_c: return PA._logo_c[ck]
        W,H=72,52
        s=pygame.Surface((W,H),pygame.SRCALPHA)
        koyu=(20,14,28);metal=(66,50,86);isik=(118,96,150);golge=(40,30,54)
        mor=(182,100,238);mor_i=(226,178,255);altin=(236,198,104);altin_k=(150,116,48)
        sil=[(6,44),(6,26),(17,8),(26,24),(36,2),(46,24),(55,8),(66,26),(66,44)]
        pygame.draw.polygon(s,metal,sil)
        if not sade:
            pygame.draw.lines(s,isik,False,[(6,26),(17,8),(26,24),(36,2),(46,24),(55,8),(66,26)],1)
            pygame.draw.polygon(s,golge,[(6,44),(6,38),(66,38),(66,44)])
        pygame.draw.polygon(s,koyu,sil,2)
        pygame.draw.rect(s,metal,(5,26,62,18));pygame.draw.rect(s,koyu,(5,26,62,18),2)
        if not sade:
            pygame.draw.line(s,isik,(7,28),(65,28),1)
            pygame.draw.line(s,golge,(7,41),(65,41),1)
            for x in (14,22,50,58):
                pygame.draw.rect(s,altin_k,(x-2,32,5,5));pygame.draw.rect(s,altin,(x-1,33,3,3))
        for x,y in ((17,8),(36,2),(55,8)):
            r=4 if not sade else 5
            pygame.draw.circle(s,altin,(x,y+2),r);pygame.draw.circle(s,altin_k,(x,y+2),r,1)
            if not sade: pygame.draw.circle(s,(255,240,190),(x-1,y+1),1)
        elmas=[(36,18),(47,34),(36,50),(25,34)]
        pygame.draw.polygon(s,mor,elmas);pygame.draw.polygon(s,koyu,elmas,2)
        pygame.draw.polygon(s,mor_i,[(36,23),(42,34),(36,45),(30,34)])
        if not sade:
            pygame.draw.polygon(s,(245,220,255),[(36,26),(39,34),(36,40),(33,34)])
        if catlak>0 and not sade:
            yol=[(36,34),(33,28),(37,22),(34,15),(37,8),(35,3)]
            asag=[(36,34),(38,40),(34,46),(37,50)]
            n=max(2,int(len(yol)*min(1.0,catlak*1.4)))
            pygame.draw.lines(s,(255,244,210),False,yol[:n],1)
            if catlak>0.6:
                m=max(2,int(len(asag)*(catlak-0.6)/0.4))
                pygame.draw.lines(s,(255,244,210),False,asag[:m],1)
        PA._logo_c[ck]=s;return s

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
        # Yuvalar EQUIP_SLOTS'tan türetiliyor: elle yazılınca yuva eklendiğinde
        # burası güncellenmiyor ve bot/muska takmak KeyError veriyordu.
        self.equipment:Dict[str,Optional[str]]={s:None for s in EQUIP_SLOTS}
        # Demircide yükseltilen parçaların kademesi: anahtar -> 0..UPGRADE_MAX
        self.upgrades:Dict[str,int]={}
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
                total+=upgrade_bonus(item_k,self.upgrades.get(item_k,0),stat)
        return total

    def equip_reason(self,item_k)->Optional[str]:
        """Eşya giyilemiyorsa nedenin çeviri anahtarı, giyilebiliyorsa None.

        Nedeni equip() döndürmüyor: eskiden hata metnini "yuvadan çıkan eşya"
        ile aynı dönüş değerinde taşıyordu, çağıran da o metni envantere eşya
        diye ekliyor ve asıl ekipmanı yok ediyordu.
        """
        if item_k not in EQUIP_ITEMS: return "ui.shop_wrong_class"
        cls_set=EQUIP_ITEMS[item_k][4]
        if cls_set and self.char_class not in cls_set: return "ui.shop_wrong_class"
        return None

    def equip(self,item_k)->Optional[str]:
        """Eşyayı yuvasına takar; yuvadan çıkan eşyanın anahtarını (yoksa None) verir.

        Giyilebilirliği çağıran equip_reason() ile önceden sorar.
        """
        slot=EQUIP_ITEMS[item_k][3]
        old=self.equipment[slot]
        self.equipment[slot]=item_k
        return old

    def unequip(self,slot)->Optional[str]:
        old=self.equipment.get(slot)
        self.equipment[slot]=None
        return old

    def heal(self,amt): self.hp=min(self.hp+amt,self.max_hp)
    def restore_mp(self,amt): self.mp=min(self.mp+amt,self.max_mp)
    def gain_xp(self,amt)->bool:
        if self.level>=MAX_LEVEL:
            self.xp=0;return False
        self.xp+=amt
        if self.xp>=self.xp_next:
            self.xp-=self.xp_next;self.level+=1;self.xp_next=xp_to_next(self.level)
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
    def __init__(self,tx,ty,kind,hp,atk,xp,agro=5,loot=None,is_boss=False,
                 boss_id=None):
        super().__init__(tx,ty)
        hp_k,atk_k=ENEMY_TUNE.get(kind,(1.0,1.0))
        hp=int(hp*hp_k);atk=int(round(atk*atk_k))
        self.kind=kind;self.max_hp=hp;self.hp=hp;self.atk=atk;self.xp_r=xp
        self.elem=ENEMY_ELEM.get(kind,"physical")
        # agro parametresi artik tur tablosundan geliyor; cagri yerlerindeki
        # dagınık degerler yok sayiliyor (bkz. AGGRO yorumu).
        a_fark,a_birak=AGGRO.get(kind,(agro,int(agro*1.6)))
        self.agro_range=a_fark*TILE;self.leash_range=a_birak*TILE
        self.loot=loot or [];self.is_boss=is_boss
        self.boss_id=boss_id          # BOSSES tablosundaki anahtar
        self.alive=True;self.state="idle";self.move_cd=0;self.frozen=0
        # Geri doğum: öldüğü yerde değil, doğduğu karede geri gelir.
        # respawn_at None ise bir daha doğmaz (boss).
        self.home=(tx,ty);self.respawn_at=None
        self.wind_up=0;self.atk_cd=0   # saldırı telegrafı
        self.wind_kind="melee"        # hazırlanan saldırının türü
        self.shoot_cd=0               # menzilli saldırı beklemesi

    def diril(self):
        """Düşmanı doğduğu karede, dolu canla geri getirir."""
        self.hp=self.max_hp;self.alive=True;self.state="idle"
        self.frozen=0;self.wind_up=0;self.atk_cd=0;self.shoot_cd=0
        self.respawn_at=None
        self.snap(*self.home)

    def draw(self,surf,cx,cy):
        if not self.alive: return
        bx=int(self.px-cx); by=int(self.py-cy)
        if not(-TILE*2<=bx<SW+TILE*2 and -TILE*2<=by<SH+TILE*2): return
        sp=PA.enemy_surf(self.kind,self.frame)
        # 2x2 çizilen dev boss'lar kareye ortalanır
        if self.kind in BIG_SPRITES: surf.blit(sp,(bx-TILE//2,by-TILE//2))
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
        # Element taşı: oyuncu neyle dövüştüğünü ve hangi saldırıyı seçeceğini
        # bir bakışta görsün. Renk ELEM_COL ile ortak.
        ec=ELEM_COL.get(getattr(self,"elem","physical"),(200,200,205))
        gs=bh+2
        pygame.draw.rect(surf,ec,(bbx-gs-2,bby-1,gs,gs))
        pygame.draw.rect(surf,BK,(bbx-gs-2,bby-1,gs,gs),1)
        if self.is_boss:
            tt=_tag_surf(f"{self.kind.upper()} {self.hp}/{self.max_hp}",UI_TX)
            surf.blit(tt,(bbx+bw//2-tt.get_width()//2,bby-12))
            et=_tag_surf(elem_name(getattr(self,"elem","physical")),ec)
            surf.blit(et,(bbx+bw//2-et.get_width()//2,bby+bh+3))

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
        # Geçit ağzı üslubu: (tx,ty) -> GATE_STYLES icinden biri
        self.gate_kind:Dict[Tuple,str]={}
        # Geçidin iki yanını çerçeveleyen engel. Verilmezse kenarda ne
        # varsa o seçilir; verilince doğal olan tercih edilir (çalı çit,
        # çam, karanlık ağaç) — her geçit taş duvarla çerçevelenmesin.
        self.frame_tile=None
        # Kopuk kalan adacıkları bağlamak için kullanılacak karo
        # (bataklıkta sığ su). None ise haritaya dokunulmaz.
        self.bridge_tile=None
    def set(self,tx,ty,tile):
        if 0<=tx<self.w and 0<=ty<self.h: self.tiles[ty][tx]=tile
    def get(self,tx,ty):
        if 0<=tx<self.w and 0<=ty<self.h: return self.tiles[ty][tx]
        return T.STONE
    def walkable(self,tx,ty): return self.get(tx,ty) in WALKABLE
    def _ts(self,tile,style=None):
        if tile in(T.WATER,T.RIVER,T.LAVA,T.SHALLOW): return PA.tile(tile,self.anim)
        ck=(tile,style)
        if ck not in self._sc: self._sc[ck]=PA.tile(tile,0,style)
        return self._sc[ck]
    def draw(self,surf,cx,cy,tick=0):
        self.anim+=1
        sx=cx//TILE;sy=cy//TILE;ex=sx+SW//TILE+2;ey=sy+SH//TILE+2
        for ty in range(max(0,sy),min(self.h,ey)):
            row=self.tiles[ty]
            for tx in range(max(0,sx),min(self.w,ex)):
                t=row[tx]
                st=self.gate_kind.get((tx,ty)) if t==T.GATE else None
                surf.blit(self._ts(t,st),(tx*TILE-cx,ty*TILE-cy))
        if self.ambient!=(0,0,0):
            _draw_ambient(surf,self.ambient,self.light_at)
        # Geçiş göstergeleri (küçük parlayan oklar — bloklama yok)
        for (tx,ty),(ddx,ddy,dname) in self.trans_hints.items():
            sx2=tx*TILE-cx;sy2=ty*TILE-cy
            if not(-TILE<=sx2<SW+TILE and -TILE<=sy2<SH+TILE): continue
            gv=int(abs(math.sin(tick*0.004))*60)+60
            hs=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
            # Geçit karesi zaten kapı gibi çiziliyor; parıltı yalnızca
            # "burası açık" demek için — eski geniş mor bant gitti.
            hs.fill((gv,int(gv*0.85),min(255,int(gv*0.45)),26))
            ang_map={(1,0):0,(-1,0):180,(0,-1):90,(0,1):270}
            ang=ang_map.get((ddx,ddy),0)
            # Ok çiz
            cx2=TILE//2;cy2=TILE//2
            pts=[(cx2+10,cy2),(cx2-6,cy2-7),(cx2-6,cy2+7)]
            import math as _m
            rad=_m.radians(ang)
            rot_pts=[(int(cx2+(px-cx2)*_m.cos(rad)-(py-cy2)*_m.sin(rad)),
                      int(cy2+(px-cx2)*_m.sin(rad)+(py-cy2)*_m.cos(rad))) for px,py in pts]
            pygame.draw.polygon(hs,(255,min(255,gv+150),min(255,gv+40),min(210,gv+110)),rot_pts)
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

# Zemin türüne göre hangi dekorlar serpiştirilir.
# NOT: Eskiden yalnızca beş zemin tipinin kaydı vardı; kül (ASH) ve buz (ICE)
# listede olmadığı için Köz Vadisi'nde dekor yoğunluğu %0.7'de kalıyordu —
# volkanik vadi bomboş görünüyordu.
_PROPS_BY_TILE = {
    T.GRASS:   ("flower","bush","grasstuft","grasstuft","rock","stump","fern"),
    T.MEADOW:  ("flower","flower","bush","grasstuft","mushroom","fern"),
    T.DIRT:    ("rock","grasstuft","stump","pebbles"),
    T.PATH:    ("pebbles","pebbles","grasstuft","rock"),
    T.GRAVEL:  ("rock","pebbles","pebbles","stalagmite"),
    T.SAND:    ("rock","bone","bone","skull","pebbles"),
    T.CRACKED: ("pebbles","bone","rock"),
    T.SNOW:    ("rock","crystal","icespike","pebbles"),
    T.ICE:     ("icespike","icespike","crystal"),
    T.ASH:     ("ember","ember","obsidian","skull","pebbles","rock"),
    T.MOSS:    ("mushroom","vine","pebbles","rock","fern"),
    T.RUBBLE:  ("rock","pebbles","skull","crate","stalagmite"),
    T.SHALLOW: ("lilypad","reed","reed"),
    T.ROAD:    ("crate","barrel","pebbles"),
    T.FLOOR:   ("rock","mushroom","crate","barrel","pot","cobweb"),
}

# Hangi haritada hangi zemin hangi çeşitlerle kırılır.
# (taban karo, [(çeşit, oran), ...]) — oran, taban karelerin ne kadarının
# o çeşide döneceği. Yalnızca TABAN karelere dokunulduğu ve bütün çeşitler
# yürünebilir olduğu için yürünebilirlik hiç değişmiyor.
GROUND_TEXTURE = {
    "map.ashveil_koyu":      [(T.GRASS,  [(T.MEADOW,0.16),(T.PATH,0.03),(T.DIRT,0.04)])],
    # Orman ve bataklıkta MOSS kullanılmıyor: o karo yosun tutmuş TAŞ
    # zemin, çimenin ortasında gri levhalar gibi duruyordu.
    "map.karanlik_orman":    [(T.GRASS,  [(T.MEADOW,0.12),(T.DIRT,0.06),(T.PATH,0.04)])],
    "map.guney_cayiri":      [(T.GRASS,  [(T.MEADOW,0.22),(T.PATH,0.04),(T.DIRT,0.03)])],
    "map.bati_nehri":        [(T.GRASS,  [(T.MEADOW,0.16),(T.PATH,0.04),(T.SHALLOW,0.02)])],
    "map.sisli_bataklik":    [(T.GRASS,  [(T.MEADOW,0.10),(T.DIRT,0.06)]),
                              (T.SAND,   [(T.SHALLOW,0.16),(T.GRAVEL,0.04)])],
    "map.kayalik_gecit":     [(T.GRAVEL, [(T.DIRT,0.10),(T.PATH,0.07),(T.CRACKED,0.07)])],
    "map.col_yolu":          [(T.SAND,   [(T.CRACKED,0.10),(T.GRAVEL,0.05)])],
    "map.buz_magara":        [(T.SNOW,   [(T.ICE,0.14),(T.GRAVEL,0.04)])],
    "map.koz_vadisi":        [(T.ASH,    [(T.CRACKED,0.12),(T.GRAVEL,0.07),(T.RUBBLE,0.06)])],
    "map.antik_harabeler":   [(T.FLOOR,  [(T.MOSS,0.16),(T.RUBBLE,0.12),(T.CRACKED,0.05)])],
    "map.koy_alti_zindani":  [(T.FLOOR,  [(T.RUBBLE,0.14),(T.MOSS,0.10)])],
    "map.golge_kalesi":      [(T.FLOOR,  [(T.RUBBLE,0.09),(T.MOSS,0.05),(T.CRACKED,0.06)])],
    "map.gizemli_kutuphane": [(T.FLOOR,  [(T.MOSS,0.07),(T.RUBBLE,0.06)])],
}


def _zemin_dokusu(m):
    """Tek tip geniş zeminleri doğal lekelerle kırar.

    Ölçüm: haritaların yarısında baskın zemin %99-100'dü ve 16 kareye kadar
    tek tip blok çıkıyordu. Lekeler nokta nokta değil, büyüyen kümeler
    hâlinde konuyor; serpiştirme ızgara gibi görünmesin.

    Tohum harita adından (crc32) üretiliyor: her açılışta aynı görünüm
    çıkar, kayıtta tutmaya gerek kalmaz.
    """
    kural = GROUND_TEXTURE.get(m.name)
    if not kural: return
    rng = random.Random(zlib.crc32((m.name + "|doku").encode("utf-8")))
    for taban, cesitler in kural:
        havuz = [(tx,ty) for ty in range(1,m.h-1) for tx in range(1,m.w-1)
                 if m.tiles[ty][tx] == taban]
        if not havuz: continue
        for cesit, oran in cesitler:
            hedef = int(len(havuz) * oran)
            konan = 0; deneme = 0
            while konan < hedef and deneme < hedef * 6 + 40:
                deneme += 1
                sx, sy = havuz[rng.randrange(len(havuz))]
                if m.tiles[sy][sx] != taban: continue
                # Küme büyüt: 2-9 kare, dört yöne yayılarak
                kume = [(sx,sy)]; sinir = [(sx,sy)]
                hacim = rng.randint(2,9)
                while sinir and len(kume) < hacim:
                    cx, cy = sinir.pop(rng.randrange(len(sinir)))
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = cx+dx, cy+dy
                        if not (1 <= nx < m.w-1 and 1 <= ny < m.h-1): continue
                        if m.tiles[ny][nx] != taban or (nx,ny) in kume: continue
                        kume.append((nx,ny)); sinir.append((nx,ny))
                        if len(kume) >= hacim: break
                for (kx,ky) in kume:
                    if (kx,ky) in m.transitions or (kx,ky) in m.chests: continue
                    m.tiles[ky][kx] = cesit; konan += 1


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
    busy|=set(m.chests)|set(m.transitions)|set(m.trans_hints)|set(m.gate_kind)
    for ty in range(m.h):
        for tx in range(m.w):
            if (tx,ty) in busy: continue
            kinds=_PROPS_BY_TILE.get(m.tiles[ty][tx])
            if not kinds or rng.random()>density: continue
            m.props.append((tx,ty,rng.choice(kinds)))

def _kopuk_baglan(m):
    """Ana bölgeden kopmuş küçük yürünebilir adacıkları bağlar.

    Sisli Bataklık'ta elle konmuş üç kum adacığı (3+2+2 kare) suyun
    ortasında kalıyordu: oyuncu görüyor, ama asla basamıyordu. Haritanın
    bildirdiği köprü karosuyla (m.bridge_tile — bataklıkta sığ su) en kısa
    yol kazılıyor. Köprü karosu verilmemiş haritalara dokunulmaz: zindan
    odalarının duvarını delmek istemeyiz.
    """
    if m.bridge_tile is None: return
    def bolgeler():
        gor=set();out=[]
        for ty in range(m.h):
            for tx in range(m.w):
                if not m.walkable(tx,ty) or (tx,ty) in gor: continue
                q=deque([(tx,ty)]);gor.add((tx,ty));b=[]
                while q:
                    cx,cy=q.popleft();b.append((cx,cy))
                    for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                        n=(cx+dx,cy+dy)
                        if n in gor or not(0<=n[0]<m.w and 0<=n[1]<m.h): continue
                        if m.walkable(*n): gor.add(n);q.append(n)
                out.append(b)
        return sorted(out,key=len,reverse=True)
    bs=bolgeler()
    if len(bs)<2: return
    ana=set(bs[0])
    for b in bs[1:]:
        # Adacıktan ana bölgeye, engellerin içinden en kısa yol
        gor={p:None for p in b};q=deque(b);varis=None
        while q:
            c=q.popleft()
            if c in ana: varis=c;break
            for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                n=(c[0]+dx,c[1]+dy)
                if n in gor or not(1<=n[0]<m.w-1 and 1<=n[1]<m.h-1): continue
                gor[n]=c;q.append(n)
        if varis is None: continue
        p=varis
        while p is not None:
            if not m.walkable(*p): m.set(p[0],p[1],m.bridge_tile)
            p=gor[p]
        ana|=set(b)


def _dagit_dusmanlar(m):
    """Düşmanların ayna düzenini bozar.

    Ölçüm: Köz Vadisi'nde 9 düşmanın 8'i, kayalık geçitte 6'nın 6'sı
    haritanın dikey ekseninde birebir aynadaydı — elle yazılmış simetri
    oynanışta hemen fark ediliyor ve yapay duruyor. Konumlar tohumlu bir
    sapmayla dağıtılıyor: tasarım niyeti (hangi bölgede hangi tür) korunuyor,
    dizilim bozuluyor. Boss yerinde kalır; odası ona göre kurulmuş.
    """
    rng=random.Random(zlib.crc32((m.name+"|dusman").encode("utf-8")))
    for e in m.enemies:
        if e.is_boss: continue
        for _ in range(12):
            nx=e.tx+rng.randint(-3,3);ny=e.ty+rng.randint(-3,3)
            if not(1<=nx<m.w-1 and 1<=ny<m.h-1): continue
            if not m.walkable(nx,ny) or (nx,ny) in m.transitions: continue
            if (nx,ny) in m.chests: continue
            e.snap(nx,ny);break


def _snap_all(m):
    _seal_border(m)          # once kenari kapat, sonra varliklari yerlestir
    _zemin_dokusu(m)         # zemin cesitliligi (yurunebilirligi degistirmez)
    _kopuk_baglan(m)         # ulasilamayan adaciklari bagla
    _dagit_dusmanlar(m)
    occ=set()
    for e in m.npcs+m.enemies:
        tx,ty=_snap(m,e.tx,e.ty);att=0
        while(tx,ty) in occ and att<30:
            tx2,ty2=_snap(m,tx+(att%5)-2,ty+(att//5)-2)
            if(tx2,ty2) not in occ: tx,ty=tx2,ty2;break
            att+=1
        e.snap(tx,ty);occ.add((tx,ty))
        if isinstance(e,Enemy): e.home=(tx,ty)

def _add_trans(m,tiles,dst,dtx,dty,ground=T.GRASS,hint_dir=(1,0)):
    """Geçiş ekle — tile normal zemin olur, görsel ok gösterilir."""
    for tx,ty in tiles:
        m.set(tx,ty,ground)
        m.transitions[(tx,ty)]=(dst,dtx,dty)
        m.trans_hints[(tx,ty)]=(hint_dir[0],hint_dir[1],dst)

# ─── Haritalar ───────────────────────────────────────────────────

# ─── Yardımcı: Harita Geçitleri ────────────────────────────────
def _gate_frame(m, axis, coord, c, half):
    """Geçidin iki yanına koyulacak engel.

    Harita kendi engelini bildiriyorsa (m.frame_tile) o kullanılır; yoksa
    kenarda zaten ne varsa o seçilir: ormanda ağaç, mağarada kaya.
    """
    if m.frame_tile is not None:
        return m.frame_tile
    for off in (half + 1, half + 2):
        for r in (c - off, c + off):
            t = m.get(coord, r) if axis == 'x' else m.get(r, coord)
            if t not in WALKABLE and t != T.CHEST:
                return t
    inner = m.get(m.w // 2, m.h // 2)
    return T.STONE if inner in (T.FLOOR, T.STONE, T.SHADOW) else T.TREE


def _seal_border(m):
    """Harita kenarını kapatır; dışarı çıkış yalnızca geçitlerden olur.

    Eskiden kenarların çoğu açıktı ve geçiş şeritleri sınırın birkaç kare
    önünde duruyordu — aradaki boşluk hem çirkin görünüyor hem de oyuncuyu
    haritanın dışına bakan boş bir şeride bırakıyordu.
    """
    ring = []
    for tx in range(m.w): ring += [(tx, 0), (tx, m.h - 1)]
    for ty in range(m.h): ring += [(0, ty), (m.w - 1, ty)]
    sayim = {}
    for (tx, ty) in ring:
        t = m.get(tx, ty)
        if t not in WALKABLE and t != T.CHEST:
            sayim[t] = sayim.get(t, 0) + 1
    if sayim:
        dolgu = max(sayim, key=sayim.get)
    else:
        ic = m.get(m.w // 2, m.h // 2)
        dolgu = T.STONE if ic in (T.FLOOR, T.STONE, T.SHADOW) else T.TREE
    for (tx, ty) in ring:
        if m.get(tx, ty) in (T.GATE, T.CHEST): continue
        m.set(tx, ty, dolgu)


# Zeminden türetilen varsayılan geçit ağzı üslubu. Haritanın kendi
# zeminine bakmak çoğu geçidi doğru yapıyor; ayrıksı olanlar (kale kapısı,
# buz ağzı, yıkık kemer) çağrı yerinde style= ile söylenir.
_GATE_STYLE_BY_GROUND = {
    T.GRASS:"arch", T.MEADOW:"arch", T.WHEAT:"arch", T.FARMLAND:"arch",
    T.DIRT:"pass", T.PATH:"pass", T.GRAVEL:"pass", T.STONE:"cave",
    T.SAND:"cave", T.SNOW:"ice", T.ICE:"ice", T.ASH:"ash",
    T.FLOOR:"ruin", T.MOSS:"ruin", T.RUBBLE:"ruin",
}


def _trans_strip(m, axis, fixed, start, end, dst, dtx, dty, ground=None, hint=None,
                 style=None):
    """Haritaya DAR, çerçeveli bir geçit açar.

    Eskiden bu fonksiyon kenar boyunca 6-10 karelik bir şerit açıyordu ve
    şerit, harita sınırının birkaç kare içinde duruyordu. Üç sorun çıkıyordu:
    şeridin önündeki boşluk kötü görünüyor, kenarın yarısı geçiş olduğu için
    yanlışlıkla harita değiştiriliyor ve varış noktası şeride bitişik
    düştüğünde oyuncu iki harita arasında sıkışıyordu.

    Artık: geçit 3 kare genişliğinde, tam sınırda duruyor, iki yanı haritanın
    kendi engeliyle çerçeveleniyor ve geçişi yalnızca en dıştaki kare
    tetikliyor — koridorda yürümek haritayı değiştirmiyor.

    axis='x' → dikey kenar (fixed=sütun), axis='y' → yatay kenar (fixed=satır)
    start/end eski şeridin aralığı; geçit bu aralığın ortasına açılıyor.
    """
    if ground is None: ground = T.GRASS
    half = 1                         # 3 kare genişlik
    c = (start + end) // 2           # eski şeridin ortası
    if axis == 'x':
        yakin = fixed < m.w // 2
        sinir = 0 if yakin else m.w - 1
        yon = (-1, 0) if yakin else (1, 0)
    else:
        yakin = fixed < m.h // 2
        sinir = 0 if yakin else m.h - 1
        yon = (0, -1) if yakin else (0, 1)
    if hint is None: hint = yon
    derinlik = abs(fixed - sinir)
    # Kenara yakınsa koridoru sınıra kadar uzat; değilse (zindan ağzı gibi
    # harita içi girişler) olduğu yerde tek kare kalsın.
    if derinlik <= 3:
        # Koridoru sınırdan içeri, AÇIK ARAZİYE DEĞENE KADAR kaz. Yalnızca
        # `fixed`e kadar kazmak koridoru kör bir cebe çıkarabiliyordu:
        # oyuncu geçitten girip 6 karelik bir çukura düşüyordu.
        ust = m.w if axis == 'x' else m.h
        adim = 1 if yakin else -1
        koridor = []; v = sinir
        for _ in range(10):
            koridor.append(v)
            ileri = v + adim
            if not (0 <= ileri < ust): break
            if abs(ileri - sinir) > derinlik:
                t = m.get(ileri, c) if axis == 'x' else m.get(c, ileri)
                if t in WALKABLE: break      # iç araziye bağlandı
            v = ileri
        kapi = sinir; kenarda = True
    else:
        koridor = [fixed]; kapi = fixed; kenarda = False

    # Kenar geçidinde çerçeve haritanın kendi engeli; harita içi girişlerde
    # (zindan ağzı) kaya: çimenin ortasında duran bir kapı gibi görünmesin.
    cerceve = _gate_frame(m, axis, kapi, c, half) if kenarda else T.STONE
    satirlar = range(c - half, c + half + 1)
    for r in satirlar:
        for v in koridor:
            if axis == 'x': m.set(v, r, ground)
            else:           m.set(r, v, ground)
    for r in (c - half - 1, c + half + 1):   # koridorun/girişin iki yanı kapalı
        for v in koridor:
            if axis == 'x': m.set(v, r, cerceve)
            else:           m.set(r, v, cerceve)
    if style is None:
        style = _GATE_STYLE_BY_GROUND.get(ground, "cave")
    for r in satirlar:               # geçişi yalnızca en dıştaki kare tetikler
        pt = (kapi, r) if axis == 'x' else (r, kapi)
        m.set(pt[0], pt[1], T.GATE)
        m.transitions[pt] = (dst, dtx, dty)
        m.gate_kind[pt] = style
        # Parlayan ok yalnızca ağzın ortasında: üç karenin üçünde birden
        # yanıp sönen ok, kapının kendi çizimini bastırıyordu.
        if r == c:
            m.trans_hints[pt] = (hint[0], hint[1], dst)


def _arrival_tile(m, tx, ty):
    """Varış karesi: yürünebilir VE komşusunda geçiş olmayan en yakın kare.

    Geçiş karesine ya da yanına düşmek oyuncuyu iki harita arasında
    sıkıştırıyordu: adım atar atmaz geri dönüyordu.
    """
    def uygun(p):
        if not m.walkable(*p) or p in m.transitions: return False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (p[0] + dx, p[1] + dy) in m.transitions: return False
        return True

    if uygun((tx, ty)): return (tx, ty)
    gorulen = {(tx, ty)}; q = deque([(tx, ty)])
    yedek = None
    while q:
        cx, cy = q.popleft()
        if uygun((cx, cy)): return (cx, cy)
        if yedek is None and m.walkable(cx, cy) and (cx, cy) not in m.transitions:
            yedek = (cx, cy)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cx + dx, cy + dy)
            if n in gorulen or not (0 <= n[0] < m.w and 0 <= n[1] < m.h): continue
            gorulen.add(n); q.append(n)
    return yedek or _snap(m, tx, ty)


def build_ashveil():
    m = GameMap(62, 52, "map.ashveil_koyu")
    m.frame_tile = T.HEDGE
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
    _path(m, 2, 24, 60, 24, T.ROAD, 2)
    _path(m, 30, 2, 30, 50, T.ROAD, 2)
    # Evler — yoldan uzak, bağlantılı
    _room(m, 16,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 34,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 16, 30, 10, 8, T.WALL, T.FLOOR, "north")
    _room(m, 34, 30, 10, 8, T.WALL, T.FLOOR, "north")
    _path(m, 20, 15, 20, 24, T.ROAD, 2)
    _path(m, 38, 15, 38, 24, T.ROAD, 2)
    _path(m, 20, 30, 20, 24, T.ROAD, 2)
    _path(m, 38, 30, 38, 24, T.ROAD, 2)
    # Sandıklar
    m.set(18, 10, T.CHEST); m.chests[(18,10)] = ["hp_pot","gold"]
    m.set(36, 10, T.CHEST); m.chests[(36,10)] = ["mp_pot","iron_sword","slime_jelly"]
    m.set(18, 32, T.CHEST); m.chests[(18,32)] = ["leather_armor","gold","hp_pot"]
    # Zindan — taş yol üzerinde
    _path(m, 28, 44, 34, 44, T.PATH, 2)
    _trans_strip(m, 'y', 46, 28, 34, "village_dungeon", 9, 5, T.DIRT, (0,1),
                 style="cave")

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
        m.set(tx, 23, T.ROAD); m.set(tx, 24, T.ROAD)
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

    # ── PAZAR MEYDANI ──
    # Köyün güneybatısı boştu; altın harcanacak tek yer iki NPC'ydi.
    _rect(m, 14, 38, 14, 10, T.ROAD)              # taş döşeli meydan
    _path(m, 27, 42, 30, 42, T.ROAD, 2)           # ana yola bağlantı
    for sx in (15, 22):                           # karşılıklı iki sıra tezgâh
        for dx in range(3):
            m.set(sx+dx, 39, T.STALL)
            m.set(sx+dx, 46, T.STALL)

    def otaci_d(f):
        D=lambda a,b:["dlg.otaci.%d"%i for i in range(a,b)]
        return D(7,13) if f.get("ch",1)>=4 else D(1,7)
    m.npcs.append(NPC(16,40,"npc.otaci_nesrin",(120,180,130),otaci_d,"oracle"))

    def avci_d(f):
        D=lambda a,b:["dlg.avci.%d"%i for i in range(a,b)]
        return D(7,13) if f.get("kill_wolf",0)>=3 else D(1,7)
    m.npcs.append(NPC(23,40,"npc.avci_doruk",(150,130,90),avci_d,"fisher"))

    def tuccar_d(f):
        D=lambda a,b:["dlg.tuccar.%d"%i for i in range(a,b)]
        return D(7,13) if f.get("ch",1)>=5 else D(1,7)
    m.npcs.append(NPC(16,45,"npc.tuccar_salim",(190,160,100),tuccar_d,"traveler"))

    def ciftci_d(f):
        D=lambda a,b:["dlg.ciftci.%d"%i for i in range(a,b)]
        return D(7,13) if f.get("kill_boar",0)>=3 else D(1,7)
    m.npcs.append(NPC(23,45,"npc.ciftci_hale",(170,150,110),ciftci_d,"farmer"))

    # NPCler
    def aldric_d(f):
        A=lambda a,b:["dlg.aldric.%d"%i for i in range(a,b)]
        if f.get("ch",1)>=6:        return A(1,7)
        if f.get("water_crystal"):  return A(7,13)
        if f.get("earth_crystal"):  return A(13,19)
        return A(19,26)
    m.npcs.append(NPC(24,19,"npc.yasli_aldric",(160,100,60),aldric_d,"elder"))
    def smith_d(f): return ["dlg.smith.%d"%i for i in range(1,8)]
    m.npcs.append(NPC(18,13,"npc.demirci_boran",(140,90,50),smith_d,"smith"))
    def inn_d(f): return ["dlg.inn.%d"%i for i in range(1,8)]
    m.npcs.append(NPC(38,13,"npc.hanci_mira",(180,130,160),inn_d,"inn"))
    def guard_d(f):
        if not f.get("speak_aldric"): return ["dlg.guard.%d"%i for i in range(1,7)]
        return ["dlg.guard.%d"%i for i in range(7,13)]
    m.npcs.append(NPC(56,22,"npc.koy_muhafizi",(100,120,180),guard_d,"guard"))
    def south_d(f): return ["dlg.south.%d"%i for i in range(1,7)]
    m.npcs.append(NPC(24,48,"npc.yolcu",(160,180,140),south_d,"traveler"))
    def west_d(f): return ["dlg.west.%d"%i for i in range(1,7)]
    # Yolun ortasinda degil kenarinda dursun: bati gecidinden donen oyuncu
    # dogrudan ona carpiyordu.
    m.npcs.append(NPC(4,27,"npc.koy_yerlisi",(140,160,180),west_d))
    m.enemies += [
        Enemy(48,12,"slime",20,4,12,agro=4,loot=["gold"]),
        Enemy(52,8, "slime",20,4,12,agro=4),
        Enemy(56,14,"goblin",35,7,22,agro=5,loot=["hp_pot"]),
        Enemy(50,16,"bat",18,5,14,agro=4),
        Enemy(54,6, "bat",18,5,14,agro=4,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_dark_forest():
    """Karanlık Orman — sabit tasarım, güney/batı çıkışları var."""
    m = GameMap(58, 48, "map.karanlik_orman", ambient=(0,20,0))
    m.frame_tile = T.DARK_TREE
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
    _path(m,0,22,58,22,T.PATH,2)
    for ty in range(48):
        for tx in range(25,33):
            if m.get(tx,ty)==T.DARK_TREE: m.set(tx,ty,T.GRASS)
    _path(m,28,0,28,48,T.PATH,2)

    # ── GEÇİŞLER ──
    # Sol → Ashveil  (y=21..27, x=2)
    _trans_strip(m,'x',2, 21,27, "ashveil",   59,24, T.GRASS,(-1,0))
    # Kuzey → Antik Harabeler  (x=25..31, y=2)
    _trans_strip(m,'y',2, 25,31, "ruins",      16,46, T.GRASS,(0,-1),style="ruin")
    # Güney → Kayalık Geçit  (x=25..31, y=46)
    _trans_strip(m,'y',46,25,31, "rocky_pass",  28, 3, T.GRASS,(0,1),style="pass")
    # Batı alt → Sisli Bataklık  (y=32..40, x=2)
    _trans_strip(m,'x',2, 32,40, "misty_swamp", 55,20, T.GRASS,(-1,0))

    # Sandıklar
    m.set(16,14,T.CHEST); m.chests[(16,14)] = ["hp_pot","fine_bow"]
    m.set(40,14,T.CHEST); m.chests[(40,14)] = ["mp_pot","power_ring","beast_pelt"]
    m.set(16,30,T.CHEST); m.chests[(16,30)] = ["leather_armor","gold","tonic_str"]

    def roland_d(f):
        R=lambda a,b:["dlg.roland.%d"%i for i in range(a,b)]
        return R(1,7) if f.get("ch",1)>=3 else R(7,14)
    m.npcs.append(NPC(22,22,"npc.sir_roland",(130,160,130),roland_d,"knight"))

    m.enemies += [
        Enemy(16,12,"wolf",35,8,20,agro=5,loot=["gold"]),
        Enemy(38,12,"wolf",35,8,20,agro=5),
        Enemy(28,34,"wolf",38,9,22,agro=5,loot=["hp_pot"]),
        Enemy(46,30,"wolf",38,9,22,agro=5),
        Enemy(42,18,"goblin",40,9,25,agro=5,loot=["hp_pot"]),
        Enemy(16,32,"skeleton",50,11,32,agro=6,loot=["mp_pot"]),
        Enemy(40,32,"goblin",45,10,28,agro=6,loot=["gold"]),
        Enemy(30,28,"wolf",42,9,22,agro=5,loot=["gold"]),
        Enemy(12,20,"spider",40, 9,28,agro=5,loot=["hp_pot"]),
        Enemy(44,26,"spider",40, 9,28,agro=5),
        Enemy(34,38,"treant",70,12,44,agro=4,loot=["gold","gold"]),
    ]
    _snap_all(m); return m


def build_rocky_pass():
    """Kayalık Geçit — Karanlık Orman'ın güneyinde, çöle bağlı."""
    m = GameMap(48, 38, "map.kayalik_gecit", ambient=(15,10,5))
    m.frame_tile = T.PINE
    _rect(m, 0, 0, 48, 38, T.STONE)
    # Yürünebilir zemin: dağ geçidinin tabanı toprak değil çakıl. Ekran
    # görüntüsünde kırmızımsı düz bir toprak ovası gibi duruyordu.
    _rect(m, 2, 2, 44, 34, T.GRAVEL)
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
                if any(m.get(tx+dx,ty+dy)==T.GRAVEL for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.RUINS_WALL)

    # Dış çerçeve
    for tx in range(48): m.set(tx,0,T.RUINS_WALL); m.set(tx,37,T.RUINS_WALL)
    for ty in range(38): m.set(0,ty,T.RUINS_WALL); m.set(47,ty,T.RUINS_WALL)
    # Kaya duvarının önünde çam kümeleri: geçit çıplak bir taş koridor
    # gibi değil, dağ yolu gibi görünsün.
    for tx,ty in [(3,3),(4,6),(3,10),(5,13),(3,17),(4,21),(3,25),(5,29),(3,33),
                  (44,3),(43,6),(44,10),(42,13),(44,17),(43,21),(44,25),(42,29),(44,33),
                  (16,2),(24,2),(32,2),(16,35),(24,35),(32,35)]:
        if m.get(tx,ty)==T.GRAVEL: m.set(tx,ty,T.PINE)
    # GEÇİŞLER
    _trans_strip(m,'y',1, 20,28, "dark_forest",  27,45, T.GRAVEL,(0,-1))
    _trans_strip(m,'y',36,20,28, "desert",        20, 4, T.GRAVEL,(0,1))
    _trans_strip(m,'x',46,15,23, "ruins",          2,21, T.GRAVEL,(1,0),style="ruin")

    m.set(8,  4, T.CHEST); m.chests[(8, 4)]  = ["hp_pot","hp_pot","gold"]
    m.set(36, 4, T.CHEST); m.chests[(36,4)]  = ["mp_pot","mp_pot_l","bone_dust"]
    m.set(24,28, T.CHEST); m.chests[(24,28)] = ["hp_pot","hp_pot_l","gold","iron_ore"]

    def scout_d(f): return ["dlg.scout.%d"%i for i in range(1,8)]
    m.npcs.append(NPC(24,16,"npc.gecit_gozcusu",(160,140,100),scout_d,"guard"))

    m.enemies += [
        Enemy(14, 6,"goblin",42,9,26,agro=5,loot=["gold"]),
        Enemy(30, 6,"goblin",42,9,26,agro=5),
        Enemy(10,18,"wolf",  38,9,22,agro=5,loot=["hp_pot"]),
        Enemy(36,18,"wolf",  38,9,22,agro=5),
        Enemy(14,26,"skeleton",52,11,30,agro=5,loot=["mp_pot"]),
        Enemy(32,26,"skeleton",52,11,30,agro=5,loot=["gold"]),
        Enemy(22,10,"bandit",  54,12,36,agro=6,loot=["hp_pot"]),
        Enemy(26,32,"bandit",  54,12,36,agro=6,loot=["gold"]),
        Enemy(40,12,"bat",     22, 7,18,agro=5),
    ]
    _snap_all(m); return m


def build_misty_swamp():
    """Sisli Bataklık — Karanlık Orman'ın batısında."""
    m = GameMap(58, 42, "map.sisli_bataklik", ambient=(10,20,10))
    m.frame_tile = T.HEDGE
    m.bridge_tile = T.SHALLOW     # adacıklara sığ sudan geçit
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
    _path(m, 2,20, 56,20, T.PATH, 2)
    _path(m,28, 2, 28,40, T.PATH, 2)
    # Kıyı şeridi
    for ty in range(42):
        for tx in range(58):
            if m.get(tx,ty)==T.GRASS:
                if any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.SAND)

    # GEÇİŞLER
    # Doğu → Karanlık Orman  (y=19..27, x=56)
    _trans_strip(m,'x',56,19,27, "dark_forest",  3,34, T.GRASS,(1,0))
    # Batı → Güney Çayırı. Eskiden burada kuzeye, Ashveil (3,24) karesine
    # çıkan TEK YÖNLÜ bir kısa yol vardı: dönüşü yoktu ve nehir geçidiyle
    # tam aynı kareye boşalıyordu. Artık dünya halka oluyor:
    # Ashveil → Çayır → Bataklık → Orman → Ashveil.
    _trans_strip(m,'x',2, 18,22, "south_meadow", 52,23, T.DIRT,(-1,0),style="arch")

    m.set(26,20, T.CHEST); m.chests[(26,20)] = ["hp_pot","mp_pot","gold"]
    m.set(48,20, T.CHEST); m.chests[(48,20)] = ["hp_pot","tonic_def","venom_sac"]
    m.set(10,20, T.CHEST); m.chests[(10,20)] = ["hp_pot","gold","gold"]
    m.set(46,20, T.CHEST); m.chests[(46,20)] = ["mp_pot","hunter_bow","spider_silk"]

    def witch_d(f): return ["dlg.witch.%d"%i for i in range(1,8)]
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
        Enemy(20,12,"spider",  42,10,29,agro=5,loot=["gold"]),
        Enemy(48,34,"treant",  76,13,47,agro=4,loot=["mp_pot"]),
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
    _trans_strip(m,'y',50, 5,14, "dark_forest",  27, 3, T.FLOOR,(0,1),style="arch")
    # Doğu → Çöl
    _trans_strip(m,'x',56,19,26, "desert",        3,27, T.FLOOR,(1,0))
    # Batı → Kayalık Geçit
    _trans_strip(m,'x',1, 19,26, "rocky_pass",   44,17, T.FLOOR,(-1,0))

    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["hp_pot","mp_pot"]
    m.set(20, 5,T.CHEST); m.chests[(20,5)] = ["arcane_staff","gold"]
    m.set(42, 5,T.CHEST); m.chests[(42,5)] = ["mage_robe","gold","scroll1"]
    m.set(6, 20,T.CHEST); m.chests[(6,20)] = ["hp_pot_l","power_ring","iron_ore","bone_dust"]
    m.set(44,44,T.CHEST); m.chests[(44,44)]= ["earth_c","hp_pot_l","elixir","titan_core"]

    def ghost_d(f):
        G=lambda a,b:["dlg.ghost.%d"%i for i in range(a,b)]
        return G(1,6) if f.get("earth_crystal") else G(6,11)
    m.npcs.append(NPC(8,19,"npc.antik_ruh",(180,200,220),ghost_d,"spirit"))
    m.enemies += [
        Enemy(6, 6,"skeleton",55,11,30,agro=5,loot=["gold"]),
        Enemy(22, 6,"skeleton",55,11,30,agro=5),
        Enemy(8, 19,"golem",  80,15,45,agro=4,loot=["gold","gold"]),
        Enemy(24,19,"skeleton",60,12,35,agro=5,loot=["hp_pot"]),
        Enemy(8, 33,"golem",  85,16,48,agro=4),
        Enemy(24,33,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(18,24,"wraith",  62,14,42,agro=6,loot=["mp_pot"]),
        Enemy(40,10,"spider",  58,12,36,agro=5,loot=["gold"]),
        Enemy(46,20,"bat",     26, 8,20,agro=5),
        Enemy(46,44,"golem", 130,20,80,agro=6,loot=["earth_c"],is_boss=True,
              boss_id="earth"),
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
    _path(m, 2,28,58,28,T.PATH,2)
    # GEÇİŞLER
    _trans_strip(m,'x',2, 26,31, "ruins",    54,21, T.SAND,(-1,0),style="ruin")
    _trans_strip(m,'x',58,26,31, "ice_cave",  4,21, T.SAND,(1,0),style="ice")
    _trans_strip(m,'y',2, 24,32, "rocky_pass",22,35, T.SAND,(0,-1),style="pass")
    _trans_strip(m,'y',42,26,32, "ember_valley",28,6, T.SAND,(0,1),style="ash")
    m.set(5, 28,T.CHEST); m.chests[(5,28)]  = ["hp_pot","hp_pot","gold"]
    m.set(54,28,T.CHEST); m.chests[(54,28)] = ["hunter_bow","gold","venom_sac","venom_sac"]
    m.set(30, 7,T.CHEST); m.chests[(30,7)]  = ["mage_focus","hp_pot_l","scroll2","oracle_lens"]
    def oracle_d(f):
        O=lambda a,b:["dlg.oracle.%d"%i for i in range(a,b)]
        if f.get("water_crystal"): return O(1,6)
        if f.get("earth_crystal"): return O(6,11)
        return O(11,16)
    m.npcs.append(NPC(30,8,"npc.oracle_nyx",(120,80,180),oracle_d,"oracle"))
    m.enemies += [
        Enemy(10,10,"scorpion",45,10,30,agro=5,loot=["gold"]),
        Enemy(48,10,"scorpion",45,10,30,agro=5),
        Enemy(30,32,"scorpion",48,11,32,agro=5,loot=["mp_pot"]),
        Enemy(16,34,"scorpion",48,11,32,agro=5),
        Enemy(10,34,"goblin",  50,11,32,agro=5,loot=["hp_pot"]),
        Enemy(48,34,"goblin",  50,11,32,agro=5,loot=["gold"]),
        Enemy(22,10,"scorpion",50,12,35,agro=6),
        Enemy(38,34,"goblin",  55,12,35,agro=5,loot=["mp_pot"]),
        Enemy(44,24,"bandit",  58,13,40,agro=6,loot=["gold"]),
        Enemy(14,24,"bandit",  58,13,40,agro=6,loot=["hp_pot"]),
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
    _trans_strip(m,'y',46,  4,12, "shadow_castle",  22,40, T.SNOW,(0,1),
                 style="door")
    m.set(5, 6,T.CHEST); m.chests[(5,6)]   = ["hp_pot","mp_pot"]
    m.set(19, 6,T.CHEST); m.chests[(19,6)] = ["scout_coat","gold","scroll3"]
    m.set(5, 19,T.CHEST); m.chests[(5,19)] = ["hp_pot_l","mp_pot_l","frost_shard"]
    m.set(38,42,T.CHEST); m.chests[(38,42)]= ["water_c","elixir","mp_pot_l","wind_feather"]
    def spirit_d(f):
        S=lambda a,b:["dlg.spirit.%d"%i for i in range(a,b)]
        return S(1,6) if f.get("water_crystal") else S(6,11)
    m.npcs.append(NPC(8,20,"npc.buz_ruhu",(180,220,255),spirit_d,"spirit"))
    m.enemies += [
        Enemy(5, 5,"ice_wolf",55,12,35,agro=5,loot=["gold"]),
        Enemy(20, 5,"ice_wolf",55,12,35,agro=5),
        Enemy(34,22,"ice_wolf",58,13,37,agro=5,loot=["hp_pot"]),
        Enemy(14,32,"ice_wolf",58,13,37,agro=5),
        Enemy(33, 5,"golem",  75,14,42,agro=4,loot=["hp_pot"]),
        Enemy(8, 19,"ice_wolf",60,13,38,agro=5),
        Enemy(22,22,"golem",  80,15,45,agro=4,loot=["mp_pot"]),
        Enemy(8, 34,"golem",  85,16,50,agro=4,loot=["hp_pot"]),
        Enemy(24,10,"bat",    30, 9,24,agro=5),
        Enemy(42,26,"bat",    30, 9,24,agro=5,loot=["gold"]),
        Enemy(18,40,"wraith", 70,15,48,agro=6,loot=["mp_pot"]),
        Enemy(40,41,"golem", 180,25,120,agro=7,loot=["water_c"],is_boss=True,
              boss_id="water"),
    ]
    _snap_all(m); return m


def build_ember_valley():
    """Köz Vadisi — çölden güneye dallanan volkanik yan bölge.

    İsteğe bağlı ve zor: ateş ve toprak düşmanlarının evi. Element sistemi
    burada iyice anlam kazanıyor, o yüzden sistemi anlatan NPC de burada.
    """
    m = GameMap(54, 44, "map.koz_vadisi", ambient=(45,12,0))
    m.frame_tile = T.STONE
    _rect(m, 0, 0, 54, 44, T.ASH)
    # Lav gölleri — yürünmez, yolu daraltıyor
    for lx,ly,ls in [(12,10,4),(40,12,4),(16,34,4),(44,33,3),(28,22,5)]:
        for ty in range(ly-ls,ly+ls+1):
            for tx in range(lx-ls,lx+ls+1):
                if (tx-lx)**2+(ty-ly)**2<=ls*ls and 2<=tx<52 and 2<=ty<42:
                    m.set(tx,ty,T.LAVA)
    # Kaya çıkıntıları
    for rx,ry,rs in [(6,22,3),(48,22,3),(26,6,3),(26,38,3)]:
        for ty in range(ry-rs,ry+rs+1):
            for tx in range(rx-rs,rx+rs+1):
                if (tx-rx)**2+(ty-ry)**2<=rs*rs and 2<=tx<52 and 2<=ty<42:
                    m.set(tx,ty,T.STONE)
    # Güvenli patikalar: lavın arasından geçen kül yolları
    _path(m, 2,22,52,22,T.PATH,2)
    _path(m,26, 2,26,42,T.PATH,2)
    # Demirhane kalıntısı
    _room(m,20,5,10,7,T.WALL,T.FLOOR,"south")

    _trans_strip(m,'y',2, 23,29, "desert", 28,38, T.ASH,(0,-1))

    m.set(7, 22,T.CHEST); m.chests[(7,22)]  = ["hp_pot","hp_pot","gold"]
    m.set(47,22,T.CHEST); m.chests[(47,22)] = ["ember_rod","gold","ember_core","ember_core"]
    m.set(25, 7,T.CHEST); m.chests[(25,7)]  = ["oak_staff","mp_pot_l","ember_core"]

    def warden_d(f):
        W=lambda a,b:["dlg.koz.%d"%i for i in range(a,b)]
        return W(7,13) if f.get("malachar_defeated") else W(1,7)
    m.npcs.append(NPC(24,8,"npc.koz_bekcisi",(220,120,60),warden_d,"smith"))

    m.enemies += [
        Enemy(10,16,"scorpion",52,12,34,agro=5,loot=["gold"]),
        Enemy(44,18,"scorpion",52,12,34,agro=5,loot=["hp_pot"]),
        Enemy(20,28,"scorpion",56,13,36,agro=6),
        Enemy(34,30,"scorpion",56,13,36,agro=6,loot=["mp_pot"]),
        Enemy( 8,34,"golem",   95,17,48,agro=5,loot=["gold"]),
        Enemy(46,34,"golem",   95,17,48,agro=5,loot=["hp_pot"]),
        Enemy(26,16,"golem",  110,19,55,agro=5,loot=["power_ring"]),
        Enemy(12,40,"shadow_knight",105,20,60,agro=6,loot=["gold"]),
        Enemy(42,40,"shadow_knight",105,20,60,agro=6,loot=["mp_pot"]),
        Enemy(16,20,"lava_imp", 54,14,38,agro=5,loot=["gold"]),
        Enemy(38,24,"lava_imp", 54,14,38,agro=5,loot=["hp_pot"]),
        Enemy(30,36,"lava_imp", 58,15,41,agro=5),
        Enemy(20,12,"lava_imp", 58,15,41,agro=5,loot=["mp_pot"]),
        # Köz Devi — ateş kristalinin muhafızı
        Enemy(26,22,"ember_titan",320,28,220,agro=8,loot=["fire_c","ember_core"],
              is_boss=True,boss_id="fire"),
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
    _trans_strip(m,'x',2, 23,30, "ice_cave",  8,44, T.FLOOR,(-1,0),style="door")
    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["hp_pot","hp_pot","mp_pot"]
    m.set(48, 5,T.CHEST); m.chests[(48,5)] = ["warrior_crest","hp_pot_l","shadow_shard"]
    m.set(5, 44,T.CHEST); m.chests[(5,44)] = ["hp_pot_l","elixir","shadow_shard","ghost_veil"]
    m.set(48,44,T.CHEST); m.chests[(48,44)]= ["mage_focus","tonic_swift","shadow_shard","ghost_veil"]
    def king_d(f):
        K=lambda a,b:["dlg.king.%d"%i for i in range(a,b)]
        return K(1,7) if f.get("malachar_defeated") else K(7,13)
    m.npcs.append(NPC(10,8,"npc.kral_alderon",(200,160,80),king_d,"knight"))
    m.enemies += [
        Enemy(8, 8,"shadow_knight",100,20,65,agro=6,loot=["hp_pot","gold"]),
        Enemy(46, 8,"shadow_knight",100,20,65,agro=6,loot=["hp_pot"]),
        Enemy(8, 44,"shadow_knight",110,22,70,agro=6,loot=["mp_pot","gold"]),
        Enemy(46,44,"shadow_knight",110,22,70,agro=6,loot=["gold"]),
        Enemy(10,26,"shadow_knight",120,24,75,agro=7,loot=["hp_pot","mp_pot"]),
        Enemy(44,26,"shadow_knight",120,24,75,agro=7),
        Enemy(16,12,"wraith",  95,20,62,agro=7,loot=["mp_pot"]),
        Enemy(40,38,"wraith",  95,20,62,agro=7,loot=["gold"]),
        Enemy(27,12,"bat",     34,11,28,agro=6),
        Enemy(27,26,"malachar",500,35,999,agro=10,loot=["gold","gold"],is_boss=True,
              boss_id="malachar"),
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
    _trans_strip(m,'y',2,  7,12, "ashveil", 29,45, T.FLOOR,(0,-1),style="cave")
    m.set(6, 5,T.CHEST); m.chests[(6,5)]   = ["hp_pot","mp_pot","gold"]
    m.set(30, 5,T.CHEST); m.chests[(30,5)] = ["war_axe","leather_armor","gold","iron_ore"]
    m.set(6, 26,T.CHEST); m.chests[(6,26)] = ["arcane_staff","mage_robe"]
    m.set(30,26,T.CHEST); m.chests[(30,26)]= ["hp_pot_l","mp_pot","swift_boots","bone_dust","iron_ore"]
    m.enemies += [
        Enemy(12, 7,"skeleton",70,14,45,agro=5,loot=["gold","gold"]),
        Enemy(28, 6,"golem",  100,18,60,agro=4,loot=["hp_pot","gold"]),
        Enemy(8, 26,"skeleton",80,16,50,agro=5,loot=["mp_pot"]),
        Enemy(30,26,"golem",  110,20,65,agro=4,loot=["gold","gold"]),
        Enemy(20,22,"skeleton",90,17,55,agro=6,loot=["hp_pot","gold"]),
        Enemy(14,14,"bat",     28, 9,22,agro=5),
        Enemy(26,16,"spider",  66,14,42,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_south_meadow():
    m = GameMap(56, 42, "map.guney_cayiri")
    m.frame_tile = T.HEDGE
    _rect(m,0,0,56,42,T.GRASS)
    _rect(m,5,10,20,14,T.FARMLAND); _rect(m,28,10,18,14,T.WHEAT)
    for tx in range(4,48): m.set(tx,9,T.FENCE); m.set(tx,25,T.FENCE)
    for ty in range(9,26): m.set(4,ty,T.FENCE); m.set(47,ty,T.FENCE)
    m.set(20,9,T.GRASS); m.set(21,9,T.GRASS)
    m.set(20,25,T.GRASS); m.set(21,25,T.GRASS)
    _room(m,5,28,14,10,T.WALL,T.FLOOR,"north")
    _room(m,22,28,10,8,T.WALL,T.FLOOR,"north")
    _path(m,20,0,20,10,T.PATH,2); _path(m,5,22,52,22,T.PATH,2)
    for ty in range(30,40):
        for tx in range(42,54):
            if (tx-48)**2+(ty-35)**2<22: m.set(tx,ty,T.WATER)
    for tx in range(56): m.set(tx,40,T.TREE); m.set(tx,41,T.TREE)
    for ty in range(42): m.set(55,ty,T.TREE)
    # GEÇİŞ
    _trans_strip(m,'y',2,  16,26, "ashveil",  22,49, T.GRASS,(0,-1),style="arch")
    # Doğu → Sisli Bataklık: çayır artık çıkmaz sokak değil
    _trans_strip(m,'x',54,20,26, "misty_swamp", 8,20, T.DIRT,(1,0),style="arch")
    m.set(8, 30,T.CHEST); m.chests[(8,30)]  = ["farm_tool","hp_pot","gold"]
    m.set(46,22,T.CHEST); m.chests[(46,22)] = ["hp_pot","mana_gem","boar_tusk","tonic_swift"]
    def farmer_d(f): return ["dlg.farmer.%d"%i for i in range(1,7)]
    m.npcs.append(NPC(10,30,"npc.ciftci_torben",(160,120,80),farmer_d,"farmer"))
    def kid_d(f): return ["dlg.kid.%d"%i for i in range(1,6)]
    m.npcs.append(NPC(35,12,"npc.ciftlik_cocugu",(180,200,160),kid_d,"child"))
    def traveler_d(f): return ["dlg.traveler.%d"%i for i in range(1,7)]
    m.npcs.append(NPC(50,22,"npc.gezgin",(140,150,180),traveler_d,"traveler"))
    m.enemies += [
        Enemy(36, 4,"boar", 40, 9,25,agro=5,loot=["gold"]),
        Enemy(20,10,"boar", 40, 9,25,agro=5,loot=["gold"]),
        Enemy(46,28,"boar", 44,10,27,agro=5),
        Enemy(14,24,"boar", 44,10,27,agro=5,loot=["hp_pot"]),
        Enemy(42, 6,"boar", 40, 9,25,agro=5),
        Enemy(8,  5,"slime",25, 5,15,agro=4,loot=["gold"]),
        Enemy(12, 5,"slime",25, 5,15,agro=4),
        Enemy(48,32,"wolf", 45,10,28,agro=5,loot=["hp_pot"]),
        Enemy(50,36,"wolf", 45,10,28,agro=5),
        Enemy(30,20,"spider",34, 8,24,agro=5,loot=["gold"]),
        Enemy(44,16,"bandit",48,11,34,agro=5,loot=["hp_pot"]),
    ]
    _snap_all(m); return m


def build_west_river():
    m = GameMap(56, 42, "map.bati_nehri", ambient=(0,10,20))
    m.frame_tile = T.HEDGE
    _rect(m,0,0,56,42,T.GRASS)
    for ty in range(42):
        for tx in range(25,31): m.set(tx,ty,T.RIVER)
    for tx in range(25,31):
        for ty in range(9,13):  m.set(tx,ty,T.BRIDGE)
        for ty in range(27,31): m.set(tx,ty,T.BRIDGE)
    _path(m,0,10,25,10,T.PATH,2); _path(m,31,10,56,10,T.PATH,2)
    _path(m,0,28,25,28,T.PATH,2); _path(m,31,28,56,28,T.PATH,2)
    _room(m,3,14,10,8,T.WALL,T.FLOOR,"east")
    for ty in range(0,8):
        for tx in range(0,10):
            if tx%3<2 and ty%3<2: m.set(tx,ty,T.TREE)
    for ty in range(33,42):
        for tx in range(35,56):
            if (tx-35)%3<2 and (ty-33)%3<2: m.set(tx,ty,T.TREE)
    # GEÇİŞLER
    _trans_strip(m,'x',54,18,28, "ashveil",  3,24, T.GRASS,(1,0))
    _trans_strip(m,'y',2, 10,16, "mystic_library",21, 4, T.GRASS,(0,-1),
                 style="door")
    m.set(5, 16,T.CHEST); m.chests[(5,16)]  = ["river_gem","mp_pot","gold"]
    m.set(46,  5,T.CHEST); m.chests[(46,5)] = ["hp_pot","hp_pot","mana_gem"]
    m.set(46, 33,T.CHEST); m.chests[(46,33)]= ["fine_bow","gold","spider_silk","tonic_def"]
    def fisher_d(f):
        F=lambda a,b:["dlg.fisher.%d"%i for i in range(a,b)]
        return F(1,7) if f.get("sq_fish_done") else F(7,14)
    m.npcs.append(NPC(6,16,"npc.balikci_riva",(100,140,180),fisher_d,"fisher"))
    def hermit_d(f): return ["dlg.hermit.%d"%i for i in range(1,7)]
    m.npcs.append(NPC(44,4,"npc.munzevi",(180,160,200),hermit_d,"hermit"))
    m.enemies += [
        Enemy(18, 4,"slime",   30, 6,18,agro=4,loot=["gold"]),
        Enemy(40, 4,"goblin",  38, 8,22,agro=5,loot=["hp_pot"]),
        Enemy(14,34,"wolf",    42, 9,25,agro=5),
        Enemy(40,34,"goblin",  45,10,28,agro=5,loot=["gold"]),
        Enemy(36,18,"skeleton",50,11,30,agro=5,loot=["mp_pot"]),
        Enemy(40,22,"skeleton",50,11,30,agro=5,loot=["gold"]),
        Enemy(20,28,"bandit",50,11,33,agro=5,loot=["gold"]),
        Enemy(46,38,"treant",72,12,45,agro=4,loot=["hp_pot"]),
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
    # Kütüphanenin tek kapısı var. Eskiden iki geçit vardı ve ikisi de
    # west_river (26,3) / (26,4) karesine, yani nehrin içine çıkıyordu.
    _trans_strip(m,'y',2, 18,26, "west_river",13, 4, T.FLOOR,(0,-1),style="door")
    m.set(5, 5,T.CHEST); m.chests[(5,5)]   = ["arcane_staff","mp_pot","gold"]
    m.set(37, 5,T.CHEST); m.chests[(37,5)] = ["mage_focus","mp_pot"]
    m.set(5, 30,T.CHEST); m.chests[(5,30)] = ["ember_rod","mp_pot_l","mp_pot","ghost_veil"]
    m.set(37,30,T.CHEST); m.chests[(37,30)]= ["hp_pot_l","mp_pot_l","travel_boots","gold","bone_dust"]
    def libr_d(f):
        n=sum(1 for k in["sq_scroll1","sq_scroll2","sq_scroll3"] if f.get(k))
        if n>=3: return ["dlg.libr.%d"%i for i in range(1,7)]
        return ["dlg.libr.7","dlg.libr.8",("dlg.libr.9",n),
                "dlg.libr.10","dlg.libr.11","dlg.libr.12"]
    m.npcs.append(NPC(21,19,"npc.kutuphaneci_elan",(140,100,200),libr_d,"scholar"))
    m.enemies += [
        Enemy(10, 8,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(28, 8,"skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(10,26,"golem",   90,16,52,agro=4,loot=["gold"]),
        Enemy(28,26,"golem",   90,16,52,agro=4,loot=["gold"]),
        Enemy(21,18,"skeleton",75,14,45,agro=6,loot=["mp_pot","gold"]),
        Enemy(14,30,"wraith",  72,15,48,agro=6,loot=["mp_pot"]),
        Enemy(32,12,"wraith",  72,15,48,agro=6,loot=["gold"]),
        # Sayfa Muhafızı — ışık kristalinin bekçisi
        Enemy(21,30,"page_warden",290,26,200,agro=8,loot=["light_c","ghost_veil"],
              is_boss=True,boss_id="light"),
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

    def draw_difficulty(self,surf,sel,tick):
        """Yeni oyun başlarken zorluk seçimi."""
        surf.fill(DKG)
        for i in range(120):
            random.seed(i*197+7);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            br=random.randint(50,150);pygame.draw.circle(surf,(br,br,br),(sx2,sy2),1)
        random.seed()
        self.txt_c(surf,T_("ui.diff_title"),SW//2,34,UI_AC,self.fxl)
        self.txt_c(surf,T_("ui.diff_subtitle"),SW//2,74,LGR,self.fmd)
        rw,rh=640,66;rx=SW//2-rw//2
        for i,d in enumerate(DIFFICULTIES):
            col=DIFF_COL.get(d[0],LGR);ry=112+i*(rh+8);sel_this=(i==sel)
            rs=pygame.Surface((rw,rh),pygame.SRCALPHA)
            if sel_this:
                gv=int(abs(math.sin(tick*0.004))*40)+35
                rs.fill((*col,24+gv));pygame.draw.rect(rs,col,(0,0,rw,rh),3)
            else:
                rs.fill((*UI_BG,190));pygame.draw.rect(rs,(*col,70),(0,0,rw,rh),2)
            surf.blit(rs,(rx,ry))
            self.txt(surf,T_(d[1]),rx+18,ry+8,col if sel_this else LGR,self.fmd)
            self.txt(surf,T_(d[1]+"_desc"),rx+18,ry+34,LGR if sel_this else GR,self.fsm)
            # Çarpanlar sağda: ne aldığın açıkça görünsün
            ozet="%s %+d%%   %s %+d%%" % (T_("ui.diff_dealt"),round((d[2]-1)*100),
                                          T_("ui.diff_taken"),round((d[3]-1)*100))
            ts=self.fsm.render(ozet,True,col if sel_this else GR)
            surf.blit(ts,(rx+rw-ts.get_width()-18,ry+10))
            if d[6]:
                ws=self.fsm.render(T_("ui.diff_permadeath"),True,(255,120,110))
                surf.blit(ws,(rx+rw-ws.get_width()-18,ry+36))
        pv=int(abs(math.sin(tick*0.004))*70)+150
        self.txt_c(surf,T_("ui.diff_hint"),SW//2,SH-40,(pv,pv,140),self.fmd)

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
        self.txt_c(surf,game_title(),SW//2,36,UI_AC,self.fxl)
        for i,(line,col) in enumerate(STORY_LINES[:lines_shown]):
            line=T_("story.%d"%(i+1),default=line) if line.strip() else line
            y=130+i*30
            if line==" " or y>SH-50: continue
            ts=self.fmd.render(line,True,col);surf.blit(ts,(SW//2-ts.get_width()//2,y))
        if lines_shown>=len(STORY_LINES):
            pv=int(abs(math.sin(tick*0.003))*80)+120
            self.txt_c(surf,T_("ui.story_next"),SW//2,SH-60,(int(pv),120,255),self.flg)

    # Açılış animasyonu zaman çizelgesi (kare cinsinden, 60 fps)
    SPLASH_IN    = 22    # siyahtan açılma
    SPLASH_RISE  = 64    # taç yükselip büyür
    SPLASH_TEXT  = 96    # başlık belirir
    SPLASH_CRACK = 116   # çatlak koşar
    SPLASH_END   = 190   # bu kareden sonra başlık ekranına geçer

    def draw_splash(self,surf,t,tick):
        """Açılış: taç yükselir, başlık belirir, taç çatlar."""
        surf.fill((8,6,12))
        # yıldızlar yavaşça belirir
        yildiz=min(1.0,t/40.0)
        for i in range(90):
            random.seed(i*331)
            sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            br=int(random.randint(40,150)*yildiz)
            if br>8: pygame.draw.circle(surf,(br,br,int(br*1.1)),(sx2,sy2),1)
        random.seed()

        yuks=min(1.0,max(0.0,(t-self.SPLASH_IN)/float(self.SPLASH_RISE-self.SPLASH_IN)))
        yuks=1-(1-yuks)**3                      # yumuşak yavaşlama
        catlak=0.0
        if t>=self.SPLASH_CRACK:
            catlak=min(1.0,(t-self.SPLASH_CRACK)/16.0)

        olcek=int(3+3*yuks)                     # 3x -> 6x
        lg=PA.logo(catlak)
        lw,lh=lg.get_width()*olcek,lg.get_height()*olcek
        ly=int(SH*0.30-lh//2+(1-yuks)*40)
        # arkada mor hale
        hale=int(90*yuks)+int(abs(math.sin(tick*0.004))*30)
        hs=pygame.Surface((lw*2,lh*2),pygame.SRCALPHA)
        for r in range(6,0,-1):
            pygame.draw.ellipse(hs,(120,60,180,max(0,hale//(7-r))),
                                (lw-r*lw//12,lh-r*lh//12,lw*r//6,lh*r//6))
        surf.blit(hs,(SW//2-lw,ly+lh//2-lh))
        big=pygame.transform.scale(lg,(lw,lh))
        if t<self.SPLASH_IN:
            big=big.copy();big.set_alpha(int(255*t/float(self.SPLASH_IN)))
        surf.blit(big,(SW//2-lw//2,ly))

        if t>=self.SPLASH_TEXT:
            a=min(255,(t-self.SPLASH_TEXT)*9)
            ts=self.fti.render(game_title(),True,UI_AC);ts.set_alpha(a)
            surf.blit(ts,(SW//2-ts.get_width()//2,ly+lh+18))
        if t>=self.SPLASH_CRACK+20:
            a=min(200,(t-self.SPLASH_CRACK-20)*6)
            sb=self.fsm.render(T_("ui.splash_by"),True,GR);sb.set_alpha(a)
            surf.blit(sb,(SW//2-sb.get_width()//2,SH-70))
            sk=self.fsm.render(T_("ui.splash_skip"),True,(90,90,110));sk.set_alpha(a)
            surf.blit(sk,(SW//2-sk.get_width()//2,SH-44))

    def draw_title(self,surf,tick):
        surf.fill(DKG)
        for i in range(150):
            random.seed(i*137);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.001+i*0.3))*100)+80
            br=(min(255,pv//2),min(255,pv//3),min(255,pv));pygame.draw.circle(surf,br,(sx2,sy2),1)
        random.seed()
        # Oyun içi amblem — açılış animasyonundaki taçla aynı.
        # Arkasındaki elips hale kaldırıldı: açılış bittikten sonra taç
        # kendi başına dursun, yalnızca hafif bir süzülme kalsın.
        lg=PA.logo(1.0);lw,lh=lg.get_width()*2,lg.get_height()*2
        suzul=int(math.sin(tick*0.0016)*3)          # yavaş yukarı-aşağı
        surf.blit(pygame.transform.scale(lg,(lw,lh)),(SW//2-lw//2,24+suzul))
        tt=self.fti.render(game_title(),True,UI_AC)
        surf.blit(self.fti.render(game_title(),True,(50,30,80)),(SW//2-tt.get_width()//2+3,143));surf.blit(tt,(SW//2-tt.get_width()//2,140))
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

    def _night_sky(self,surf,tick,n=160,warm=True):
        """Kapanış ekranlarının ortak arka planı: yavaşça nefes alan yıldızlar."""
        surf.fill(DKG)
        for i in range(n):
            random.seed(i*313);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.002+i*0.5))*110)+70
            col=(pv,int(pv*0.85),60) if warm else (int(pv*0.8),int(pv*0.9),pv)
            pygame.draw.circle(surf,col,(sx2,sy2),1)
        random.seed()

    # ── Boss kapanış sahnesi ─────────────────────────────────────
    # Malachar dışındaki boss'lar sessizce ölüyordu. Artık her ana boss
    # düştüğünde mühürden bir parça kırılıyor: silüet çatlıyor, karanlık
    # zerrelere dağılıyor, yerinde bir kristal kalıyor.
    BS_CRACK   = 26    # çatlaklar koşmaya başlar
    BS_SHATTER = 72    # silüet dağılır
    BS_CRYSTAL = 118   # kristal belirir
    BS_TEXT    = 154   # anlatı gelir

    def draw_boss_scene(self,surf,sahne,tick):
        t=sahne["t"];col=sahne["col"]
        surf.fill((6,5,10))
        # Dağılan karanlığın arkasındaki yıldızlar
        self._night_sky(surf,tick,90,warm=False)
        cx,cy=SW//2,int(SH*0.38)

        # ── Silüet ──
        if t<self.BS_SHATTER+46:
            sp=PA.enemy_surf(sahne["kind"],tick//3)
            olcek=7 if sahne["kind"] in BIG_SPRITES else 10
            w,h=sp.get_width()*olcek//2,sp.get_height()*olcek//2
            big=pygame.transform.scale(sp,(w,h)).copy()
            if t>=self.BS_SHATTER:
                sol=max(0,255-int((t-self.BS_SHATTER)*6))
                big.set_alpha(sol)
            titre=0
            if self.BS_CRACK<=t<self.BS_SHATTER:
                titre=int(math.sin(t*1.7)*3)
            surf.blit(big,(cx-w//2+titre,cy-h//2))
            # Çatlaklar
            if t>=self.BS_CRACK:
                ilerle=min(1.0,(t-self.BS_CRACK)/float(self.BS_SHATTER-self.BS_CRACK))
                random.seed(sahne["tohum"])
                for _ in range(7):
                    # Çatlaklar gövdenin ortasından başlasın; kenardan
                    # başlayınca silüetin yanından akıp gidiyordu.
                    x1=cx+random.randint(-w//3,w//3);y1=cy-h//3
                    pts=[(x1,y1)]
                    for _k in range(5):
                        x1=max(cx-w//2,min(cx+w//2,x1+random.randint(-9,9)))
                        y1+=int(h/7)
                        pts.append((x1,y1))
                    n=max(2,int(len(pts)*ilerle))
                    pygame.draw.lines(surf,(255,246,220),False,pts[:n],2)
                random.seed()

        # ── Dağılan zerreler ──
        if t>=self.BS_SHATTER:
            random.seed(sahne["tohum"]+7)
            ilerle=(t-self.BS_SHATTER)/46.0
            for _ in range(46):
                ang=random.random()*math.tau;hiz=random.randint(40,170)
                px=int(cx+math.cos(ang)*hiz*ilerle)
                py=int(cy+math.sin(ang)*hiz*ilerle-ilerle*ilerle*40)
                a=max(0,int(210*(1-ilerle)))
                if a<=0: continue
                zs=pygame.Surface((6,6),pygame.SRCALPHA)
                pygame.draw.circle(zs,(60,30,80,a),(3,3),3)
                pygame.draw.circle(zs,(150,90,200,a),(3,3),1)
                surf.blit(zs,(px,py))
            random.seed()

        # ── Kristal ──
        if t>=self.BS_CRYSTAL:
            k=min(1.0,(t-self.BS_CRYSTAL)/30.0)
            r=int(10+34*k)
            nb=int(abs(math.sin(tick*0.004))*22)
            # Yumuşak hale: beş kalın halka yerine ince kademeler.
            # Az sayıda büyük daire gözle görülür bantlar bırakıyordu.
            # NOT: BLEND_RGBA_ADD alfayı dikkate almadan RGB ekliyor, bu
            # yüzden hale masif bir diske dönüşüyordu — normal harmanlama.
            hs=pygame.Surface((r*6,r*6),pygame.SRCALPHA)
            dis=r*3
            for i in range(dis,0,-2):
                a=int((70+nb)*(1.0-i/float(dis))**2.4)
                if a<=0: continue
                pygame.draw.circle(hs,(col[0],col[1],col[2],a),(dis,dis),i)
            surf.blit(hs,(cx-dis,cy-dis))
            pts=[(cx,cy-r),(cx+int(r*0.62),cy),(cx,cy+r),(cx-int(r*0.62),cy)]
            pygame.draw.polygon(surf,col,pts)
            pygame.draw.polygon(surf,(16,12,20),pts,2)
            ic=[(cx,cy-r//2),(cx+r//4,cy),(cx,cy+r//2),(cx-r//4,cy)]
            pygame.draw.polygon(surf,(min(255,col[0]+60),min(255,col[1]+60),
                                      min(255,col[2]+60)),ic)

        # ── Anlatı ──
        if t>=self.BS_TEXT:
            a=min(255,(t-self.BS_TEXT)*8)
            ad=self.fxl.render(T_(sahne["name"]),True,col);ad.set_alpha(a)
            surf.blit(ad,(SW//2-ad.get_width()//2,SH-220))
            satir=T_(sahne["lines"][sahne["page"]])
            for i,par in enumerate(self._wrap(satir,self.fmd,SW-200)):
                ts=self.fmd.render(par,True,UI_TX);ts.set_alpha(a)
                surf.blit(ts,(SW//2-ts.get_width()//2,SH-162+i*34))
            self.txt_c(surf,"%d/%d"%(sahne["page"]+1,len(sahne["lines"])),
                       SW//2,SH-66,GR,self.fsm)
            pv=int(abs(math.sin(tick*0.003))*80)+120
            self.txt_c(surf,T_("ui.story_next"),SW//2,SH-40,(pv,120,255),self.fmd)
        elif t>self.BS_CRACK:
            self.txt_c(surf,T_("ui.splash_skip"),SW//2,SH-40,(80,80,100),self.fsm)

    def _wrap(self,metin,font,genislik):
        """Uzun cümleyi kutuya sığacak satırlara böler."""
        kelimeler=metin.split();satirlar=[];cur=""
        for k in kelimeler:
            dene=(cur+" "+k).strip()
            if font.size(dene)[0]<=genislik: cur=dene
            else:
                if cur: satirlar.append(cur)
                cur=k
        if cur: satirlar.append(cur)
        return satirlar or [""]

    def draw_epilogue(self,surf,satirlar,sayfa,toplam,tick):
        """Kapanış anlatısı — hikâye ekranıyla aynı dilde, sayfa sayfa."""
        self._night_sky(surf,tick,110,warm=False)
        self.txt_c(surf,T_("epi.title"),SW//2,40,UI_AC,self.fxl)
        y=SH//2-len(satirlar)*18
        for k in satirlar:
            t=T_(k)
            ts=self.fmd.render(t,True,UI_TX)
            surf.blit(ts,(SW//2-ts.get_width()//2,y));y+=36
        self.txt_c(surf,"%d/%d"%(sayfa+1,toplam),SW//2,SH-86,GR,self.fsm)
        pv=int(abs(math.sin(tick*0.003))*80)+120
        self.txt_c(surf,T_("ui.story_next"),SW//2,SH-56,(pv,120,255),self.fmd)

    def draw_victory(self,surf,tick,stats=None,rank=None):
        self._night_sky(surf,tick,200,warm=True)
        gv=int(abs(math.sin(tick*0.002))*60)+80
        self.txt_c(surf,T_("victory_title"),SW//2,54,(255,gv+80,gv//2),self.fti)
        if rank: self.txt_c(surf,T_(rank),SW//2,132,UI_GD,self.fxl)
        self.txt_c(surf,T_("victory_sub"),SW//2,180,UI_TX,self.fmd)
        # Yolculuğun özeti: oyuncunun ne yaptığı tek karede görünsün
        if stats:
            pw,ph=420,180;px=SW//2-pw//2;py=224
            self.panel(surf,px,py,pw,ph)
            for i,(ad,deger) in enumerate(stats):
                yy=py+16+i*28
                self.txt(surf,ad,px+22,yy,LGR,self.fmd)
                ts=self.fmd.render(str(deger),True,UI_GD)
                surf.blit(ts,(px+pw-22-ts.get_width(),yy))
        self.txt_c(surf,T_("victory_sub2"),SW//2,SH-92,UI_TX,self.fsm)
        self.txt_c(surf,T_("victory_menu"),SW//2,SH-56,
                   (int(abs(math.sin(tick*0.003))*100)+120,100,255),self.fmd)

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

    def draw_shop_marker(self,surf,tx,ty,cx,cy,tick):
        """Dükkâncının üstünde para işareti — alışveriş yapılabildiği belli olsun."""
        sx=tx*TILE-cx+TILE//2;sy=ty*TILE-cy-24
        if not(-20<=sx<SW+20 and -20<=sy<SH): return
        bob=int(abs(math.sin(tick*0.004))*3)
        pygame.draw.circle(surf,(40,30,10),(sx,sy-bob+6),7)
        pygame.draw.circle(surf,(235,195,70),(sx,sy-bob+5),6)
        pygame.draw.circle(surf,(180,140,40),(sx,sy-bob+5),6,1)
        t=self.fsm.render("$",True,(90,65,15))
        surf.blit(t,(sx-t.get_width()//2,sy-bob+1))

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

    @staticmethod
    def pause_opts():
        """Her çizimde yeniden kuruluyor: liste sabit olunca dil değişince
        duraklatma menüsü eski dilde kalıyordu."""
        return [
            (T_("ui.pause_resume"),   (100,220,100)),
            (T_("ui.pause_save"),     (120,200,240)),
            (T_("ui.pause_controls"), (240,210,120)),
            (T_("ui.pause_settings"), (180,140,250)),
            (T_("ui.pause_menu"),     (220,150,60)),
            (T_("ui.pause_quit"),     (220,80,80)),
        ]

    def draw_pause(self,surf,tick,pause_sel=0):
        """ESC ile açılan duraklama menüsü."""
        self.dim(surf,160)
        pw,ph=360,270; px=SW//2-pw//2; py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt_c(surf,T_("ui.paused"),px+pw//2,py+14,UI_AC,self.flg)
        for i,(label,col) in enumerate(self.pause_opts()):
            oy=py+58+i*40
            sel_this=(i==pause_sel)
            ss=pygame.Surface((pw-28,34),pygame.SRCALPHA)
            ss.fill((*col,70 if sel_this else 25))
            pygame.draw.rect(ss,col if sel_this else (*col[:3],80),(0,0,pw-28,34),2 if sel_this else 1)
            surf.blit(ss,(px+14,oy))
            self.txt_c(surf,label,px+pw//2,oy+7,col if sel_this else LGR,self.fmd)

    # ── Kontrol tanıtımı ─────────────────────────────────────────
    # Oyun içindeki soluk tuş listesi yerine, oyuna başlarken bir kez açılan
    # gerçek bir klavye görseli. Duraklatma menüsünden tekrar açılabiliyor.
    def keycap(self,surf,x,y,w,h,label,vurgu=False,ok=None):
        """Tek bir tuş kapağı çizer. `ok` verilirse yazı yerine üçgen çizilir
        (ok tuşlarının glifi her yazı tipinde yok)."""
        yuz   = (74,80,96) if not vurgu else (96,86,52)
        kenar = (150,158,178) if not vurgu else (240,210,120)
        pygame.draw.rect(surf,(18,19,26),(x+2,y+3,w,h),border_radius=5)
        pygame.draw.rect(surf,yuz,(x,y,w,h),border_radius=5)
        pygame.draw.rect(surf,(int(yuz[0]*1.3),int(yuz[1]*1.3),int(yuz[2]*1.25)),
                         (x+2,y+2,w-4,max(3,h//2-2)),border_radius=4)
        pygame.draw.rect(surf,kenar,(x,y,w,h),2,border_radius=5)
        if ok:
            cx,cy=x+w//2,y+h//2;r=7
            uc={"up":[(cx,cy-r),(cx-r,cy+r-2),(cx+r,cy+r-2)],
                "down":[(cx,cy+r),(cx-r,cy-r+2),(cx+r,cy-r+2)],
                "left":[(cx-r,cy),(cx+r-2,cy-r),(cx+r-2,cy+r)],
                "right":[(cx+r,cy),(cx-r+2,cy-r),(cx-r+2,cy+r)]}[ok]
            pygame.draw.polygon(surf,(245,246,250),uc)
        else:
            f=self.fsm if len(label)>2 else self.fmd
            t=f.render(label,True,(245,246,250))
            surf.blit(t,(x+w//2-t.get_width()//2,y+h//2-t.get_height()//2))
        return pygame.Rect(x,y,w,h)

    def draw_tutorial(self,surf,tick):
        self.dim(surf,185)
        pw,ph=720,500;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt_c(surf,T_("ui.tut_title"),px+pw//2,py+14,UI_AC,self.flg)

        # ── Sol: hareket tuşları ──
        lx,ly=px+40,py+70
        self.txt(surf,T_("ui.tut_move"),lx,ly,UI_GD,self.fmd)
        k=34;g=4
        self.keycap(surf,lx+k+g,      ly+24,k,k,"W",True)
        self.keycap(surf,lx,          ly+24+k+g,k,k,"A",True)
        self.keycap(surf,lx+k+g,      ly+24+k+g,k,k,"S",True)
        self.keycap(surf,lx+2*(k+g),  ly+24+k+g,k,k,"D",True)
        ax=lx+170
        self.txt_c(surf,T_("ui.tut_or"),lx+140,ly+24+k+g+9,GR,self.fsm)
        self.keycap(surf,ax+k+g,      ly+24,k,k,"",ok="up")
        self.keycap(surf,ax,          ly+24+k+g,k,k,"",ok="left")
        self.keycap(surf,ax+k+g,      ly+24+k+g,k,k,"",ok="down")
        self.keycap(surf,ax+2*(k+g),  ly+24+k+g,k,k,"",ok="right")

        # ── Saldırı: geniş boşluk tuşu ──
        sy=ly+24+2*(k+g)+22
        self.keycap(surf,lx,sy,236,k,"SPACE",True)
        self.txt(surf,T_("ui.tut_attack"),lx+248,sy+8,UI_TX,self.fmd)

        # ── Sağ sütun: eylem tuşları ──
        satirlar=[("E",T_("ui.tut_interact")),("1-4",T_("ui.tut_ability")),
                  ("I",T_("ui.tut_inventory")),("Q",T_("ui.tut_quests")),
                  ("M",T_("ui.tut_minimap")),  ("U",T_("ui.tut_stats")),
                  ("F1",T_("ui.tut_settings")),("ESC",T_("ui.tut_pause")),
                  ("F11",T_("ui.tut_fullscreen"))]
        cy0=sy+k+26
        for i,(tus,ad) in enumerate(satirlar):
            col=i//5; row=i%5
            bx=px+40+col*340; by=cy0+row*38
            self.keycap(surf,bx,by,46,30,tus)
            self.txt(surf,ad,bx+58,by+7,LGR,self.fsm)

        self.txt_c(surf,T_("ui.tut_again"),px+pw//2,py+ph-44,GR,self.fsm)
        pulse=int(abs(math.sin(tick*0.005))*70)+170
        self.txt_c(surf,T_("ui.tut_start"),px+pw//2,py+ph-26,(pulse,pulse,120),self.fmd)

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
            (T_("set_minimap"),    T_("set_on") if CFG.minimap else T_("set_off"), "minimap"),
            (T_("ui.diff_title"),  diff_name(), "difficulty"),
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

    # ── Mini harita ──────────────────────────────────────────────
    MINI_W,MINI_H = 168,140      # panel içindeki en büyük çizim alanı
    _mini_terrain:Dict={}        # (harita adı, ölçek) -> statik zemin yüzeyi
    _mini_col:Dict={}            # kare türü -> mini haritadaki renk

    @classmethod
    def mini_tile_col(cls,k):
        """Karenin mini haritadaki rengi: asıl doku karesinin ortalaması.

        Elle renk tablosu tutmuyoruz; doku değişirse mini harita kendiliğinden
        uyuyor. Oyunun paleti koyu olduğu için ortalamalar olduğu gibi
        kullanılınca mini harita okunmuyordu: yürünen kareler açılıyor,
        yürünemeyenler koyulaşıyor. Amaç sadakat değil, yolun görünmesi.
        """
        if k not in cls._mini_col:
            try: c=tuple(pygame.transform.average_color(PA.tile(k))[:3])
            except Exception: c=(90,90,90)
            f=1.7 if k in WALKABLE else 0.45
            cls._mini_col[k]=tuple(min(255,int(v*f)) for v in c)
        return cls._mini_col[k]

    def draw_minimap(self,surf,m,player,tick):
        """Sağ üstte mini harita. Zemin önbellekte; yalnız işaretler her karede."""
        ppt=max(2,min(self.MINI_W//m.w,self.MINI_H//m.h))   # kare başına piksel
        key=(m.name,ppt)
        base=self._mini_terrain.get(key)
        if base is None:
            flat=pygame.Surface((m.w,m.h))
            for ty in range(m.h):
                row=m.tiles[ty]
                for tx in range(m.w):
                    t=row[tx]
                    # Sandık karesi açılınca zemine dönüşüyor: zemini sabit
                    # tutup sandığı işaret olarak çiziyoruz, önbellek bayatlamasın.
                    flat.set_at((tx,ty),self.mini_tile_col(T.FLOOR if t==T.CHEST else t))
            base=pygame.transform.scale(flat,(m.w*ppt,m.h*ppt))
            self._mini_terrain[key]=base
        mw,mh=base.get_size();pad=5
        px=SW-mw-pad*2-6;py=6
        self.panel(surf,px,py,mw+pad*2,mh+pad*2)
        surf.blit(base,(px+pad,py+pad))

        def dot(tx,ty,col,grow=0):
            pygame.draw.rect(surf,col,(px+pad+tx*ppt-grow,py+pad+ty*ppt-grow,
                                       ppt+grow*2,ppt+grow*2))

        for (tx,ty) in m.transitions: dot(tx,ty,UI_PR)     # çıkışlar
        for (tx,ty) in m.chests:      dot(tx,ty,UI_GD)     # sandıklar
        for n in m.npcs:              dot(n.tx,n.ty,UI_CY)
        for e in m.enemies:
            if e.alive:               dot(e.tx,e.ty,UI_RD)
        # Oyuncu: nabız gibi büyüyen beyaz nokta — kalabalıkta kaybolmasın
        dot(player.tx,player.ty,WH,1 if (tick//20)%2 else 0)
        pygame.draw.rect(surf,UI_BD,(px+pad,py+pad,mw,mh),1)

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
        # Saldırı elementi: silah değişince ne olduğunu görmek lazım
        ael=WEAPON_ELEM.get(st.equipment.get("weapon")) or CLASS_ELEM.get(st.char_class,"physical")
        ac=ELEM_COL.get(ael,(200,200,205))
        pygame.draw.rect(surf,ac,(214,73,8,8));pygame.draw.rect(surf,BK,(214,73,8,8),1)
        self.txt(surf,elem_name(ael),226,72,ac,self.fsm)
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
        # Eskiden burada soluk bir tuş listesi vardı. Yerini oyuna başlarken
        # bir kez açılan klavye tanıtımı aldı (duraklatma → Kontroller).

    SHOP_ROWS = 7        # ekranda aynı anda görünen satır

    def draw_shop(self,surf,player,shop,npc_key,tab,sel,tick,msg=None):
        """Dükkân: solda satılanlar, sağda çantandakiler.

        Sınıfına uymayan ekipman gri gösterilir — parayı boşa vermeyesin.
        """
        self.dim(surf)
        pw,ph=680,430;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt(surf,T_(npc_key),px+16,py+8,UI_GD,self.flg)
        gold_s="%s: %d"%(T_("gold"),player.stats.gold)
        self.txt(surf,gold_s,px+pw-self.fmd.size(gold_s)[0]-16,py+14,UI_GD,self.fmd)

        # Sekmeler
        sekmeler=[T_(x) for x in self.shop_tabs(shop)]
        tw=150 if len(sekmeler)<3 else 128
        for i,label in enumerate(sekmeler):
            active=(i==tab)
            tx0=px+16+i*(tw+6)
            ts=pygame.Surface((tw,24),pygame.SRCALPHA)
            ts.fill((*UI_AC,80) if active else (*UI_BD,30))
            pygame.draw.rect(ts,UI_AC if active else UI_BD,(0,0,tw,24),2)
            surf.blit(ts,(tx0,py+46))
            self.txt(surf,label,tx0+8,py+50,UI_AC if active else GR,self.fss,shadow=False)
            if not active:
                pulse=int(abs(math.sin(tick*0.005))*80)+140
                b=self.fsm.render("[TAB]",True,(pulse,pulse,120))
                surf.blit(b,(tx0+tw-b.get_width()-6,py+52))

        if tab==2:
            self._draw_upgrade_tab(surf,player,px,py,pw,ph,sel,msg)
            return
        rows=self.shop_rows(player,shop,tab)
        top=max(0,min(sel-self.SHOP_ROWS//2,len(rows)-self.SHOP_ROWS))
        y=py+82
        for i in range(top,min(len(rows),top+self.SHOP_ROWS)):
            key,price,ok=rows[i]
            sel_this=(i==sel)
            rs=pygame.Surface((pw-32,40),pygame.SRCALPHA)
            rs.fill((*UI_AC,55) if sel_this else (*UI_BD,20))
            if sel_this: pygame.draw.rect(rs,UI_AC,(0,0,pw-32,40),2)
            surf.blit(rs,(px+16,y))
            itm=ALL_ITEMS.get(key)
            col=itm[1] if itm else WH
            pygame.draw.rect(surf,col,(px+24,y+8,24,24))
            pygame.draw.rect(surf,WH,(px+24,y+8,24,24),1)
            if itm and itm[2]=="equip":
                surf.blit(PA.equip_icon(itm[3],col),(px+22,y+6))
            name_col=WH if ok else (95,90,95)
            self.txt(surf,item_name(key),px+58,y+6,name_col,self.fss)
            self.txt(surf,item_desc(key) or "",px+58,y+22,GR,self.fsm)
            ps="%d %s"%(price,T_("gold"))
            self.txt(surf,ps,px+pw-self.fss.size(ps)[0]-26,y+12,
                     UI_GD if ok else (120,90,60),self.fss)
            y+=42

        if not rows:
            self.txt(surf,T_("ui.shop_empty"),px+30,py+100,GR,self.fss)
        if len(rows)>self.SHOP_ROWS:
            self.txt(surf,"%d/%d"%(sel+1,len(rows)),px+pw-70,py+52,GR,self.fsm)

        # Handa konaklama
        hint=T_("ui.shop_keys_buy") if tab==0 else T_("ui.shop_keys_sell")
        if shop.get("rest"):
            self.txt(surf,T_("ui.shop_rest",REST_PRICE),px+16,py+ph-40,UI_CY,self.fss)
        if msg:
            self.txt_c(surf,msg[0],px+pw//2,py+ph-62,msg[1],self.fmd)
        self.txt(surf,hint,px+16,py+ph-20,GR,self.fsm)

    def _draw_upgrade_tab(self,surf,player,px,py,pw,ph,sel,msg):
        """Demirci tezgâhı: giyili parçaların kademesi, bedeli ve kazancı."""
        st=player.stats
        elde=sum(1 for k in player.inventory if k in MATERIALS)
        bilgi=T_("ui.upg_materials",elde)
        self.txt(surf,bilgi,px+16,py+78,UI_CY,self.fss)
        rows=self.upgrade_rows(player)
        if not rows:
            self.txt(surf,T_("ui.upg_nothing"),px+30,py+110,GR,self.fss)
            self.txt(surf,T_("ui.shop_keys_upgrade"),px+16,py+ph-20,GR,self.fsm)
            return
        y=py+102
        for i,(k,altin,mal,ok,lvl) in enumerate(rows):
            sel_this=(i==sel)
            rs=pygame.Surface((pw-32,46),pygame.SRCALPHA)
            rs.fill((*UI_AC,55) if sel_this else (*UI_BD,20))
            if sel_this: pygame.draw.rect(rs,UI_AC,(0,0,pw-32,46),2)
            surf.blit(rs,(px+16,y))
            itm=ALL_ITEMS.get(k);col=itm[1] if itm else WH
            pygame.draw.rect(surf,col,(px+24,y+10,24,24))
            pygame.draw.rect(surf,WH,(px+24,y+10,24,24),1)
            surf.blit(PA.equip_icon(EQUIP_ITEMS[k][3],col),(px+22,y+8))
            ad=item_name(k)+(" +%d"%lvl if lvl else "")
            self.txt(surf,ad,px+58,y+6,WH if ok or lvl>=UPGRADE_MAX else (150,145,150),self.fss)
            # Kademenin ne kattigi
            bonus=EQUIP_ITEMS[k][2]
            parca=[]
            for st_k in sorted(bonus,key=lambda x:(-bonus[x],x)):
                top_=bonus[st_k]+upgrade_bonus(k,lvl,st_k)
                # En üst kademede artık kazanç yok: "(+1)" yazmak
                # alınamayacak bir şey vaat ediyordu.
                art=0 if lvl>=UPGRADE_MAX else                     upgrade_bonus(k,lvl+1,st_k)-upgrade_bonus(k,lvl,st_k)
                parca.append("%s+%d%s"%(st_k.upper(),top_,(" (+%d)"%art) if art else ""))
            self.txt(surf," / ".join(parca),px+58,y+24,GR,self.fsm)
            if lvl>=UPGRADE_MAX:
                sag=T_("ui.upg_max")
                self.txt(surf,sag,px+pw-self.fss.size(sag)[0]-26,y+15,UI_GN,self.fss)
            else:
                sag="%d %s  +  %d %s"%(altin,T_("gold"),mal,T_("ui.upg_mat_unit"))
                self.txt(surf,sag,px+pw-self.fss.size(sag)[0]-26,y+15,
                         UI_GD if ok else (120,90,60),self.fss)
            y+=50
        if msg:
            self.txt_c(surf,msg[0],px+pw//2,py+ph-62,msg[1],self.fmd)
        self.txt(surf,T_("ui.shop_keys_upgrade"),px+16,py+ph-20,GR,self.fsm)

    @staticmethod
    def shop_tabs(shop):
        """Bu dükkânda hangi sekmeler var."""
        t=["ui.shop_buy","ui.shop_sell"]
        if shop.get("upgrade"): t.append("ui.shop_upgrade")
        return t

    @staticmethod
    def upgrade_rows(player):
        """Giyili parçalar: (anahtar, altın, malzeme, yapılabilir mi, kademe)."""
        st=player.stats
        elde=sum(1 for k in player.inventory if k in MATERIALS)
        out=[]
        for slot in EQUIP_SLOTS:
            k=st.equipment.get(slot)
            if not k or k not in EQUIP_ITEMS: continue
            lvl=st.upgrades.get(k,0)
            bedel=upgrade_cost(lvl)
            if bedel is None:
                out.append((k,0,0,False,lvl));continue
            altin,mal=bedel
            out.append((k,altin,mal,st.gold>=altin and elde>=mal,lvl))
        return out

    @staticmethod
    def shop_rows(player,shop,tab):
        """(anahtar, fiyat, islem yapilabilir mi) listesi."""
        st=player.stats
        if tab==0:
            out=[]
            for k in shop["stock"]:
                ok=st.gold>=item_price(k)
                if k in EQUIP_ITEMS:
                    cls_set=EQUIP_ITEMS[k][4]
                    if cls_set and st.char_class not in cls_set: ok=False
                out.append((k,item_price(k),ok))
            return out
        seen=[]
        for k in player.inventory:
            if k not in seen: seen.append(k)
        return [(k,sell_price(k),True) for k in seen]

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
        # Açılış animasyonu yalnızca uygulama başlarken; ana menüye dönüşte
        # (_reset) doğrudan başlık ekranı geliyor.
        self.state="splash";self.splash_t=0
        SoundManager.play_music("victory")

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
            "ember_valley":build_ember_valley(),
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
            # İsteğe bağlı kristaller: ana zinciri kilitlemiyor
            "fire_crystal":False,"light_crystal":False,
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
        self.epi_pages=[];self.epi_page=0            # kapanış sayfaları
        self.boss_scene=None                         # boss kapanış sahnesi
        self.splash_t=0                              # açılış animasyonu sayacı
        self.diff_sel=DIFF_IDS.index(CFG.data.get("difficulty","normal")) \
            if CFG.data.get("difficulty","normal") in DIFF_IDS else 1
        self.permadeath_hit=False
        self.shop_npc=None;self.shop_tab=0;self.shop_sel=0;self.shop_msg=None
        self.projectiles:List[Projectile]=[]
        self.settings_sel=0  # Ayarlar menüsü seçimi
        self.settings_open=False
        self.pause_open=False
        self._pause_sel=0  # Pause menüsü: 0=devam,1=ayarlar,2=ana menu,3=cikis

    # Oyun dünyasının (HUD, bildirimler) çizildiği durumlar
    HUD_STATES = ("playing","dialog","inventory","quest_log","levelup_alloc","shop")

    # Harita → müzik teması eşleşmesi
    MAP_MUSIC = {
        "ashveil":"village","dark_forest":"forest","ruins":"dungeon",
        "desert":"battle","ice_cave":"dungeon","shadow_castle":"castle",
        "village_dungeon":"dungeon","south_meadow":"village",
        "west_river":"village","mystic_library":"library",
        "rocky_pass":"dungeon","misty_swamp":"forest",
        "ember_valley":"battle",
    }

    def _start_game(self):
        st=self.temp_stats;st.hp=st.max_hp;st.mp=st.max_mp
        sx,sy=_snap(self.maps["ashveil"],29,25)
        self.player=Player(sx,sy,st)
        self.cur_key="ashveil";self.cur_map=self.maps["ashveil"]
        # Kontrol tanıtımı yalnızca ilk oyunda; tercih ayarlarda saklanıyor.
        self.state="playing" if CFG.tutorial_seen else "tutorial"
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
        # İki adımda bir: aynı ses saniyede 7 kez çalınca tekrar yoruyor
        self._step_n=getattr(self,"_step_n",0)+1
        if self._step_n%2==0: SoundManager.play("walk")
        pt=(p.tx,p.ty)
        if pt in self.cur_map.transitions:
            dst,tx2,ty2=self.cur_map.transitions[pt];self._start_trans(dst,tx2,ty2)
        return True

    def _start_trans(self,dst,tx,ty):
        self.pending_trans=(dst,tx,ty);self.transitioning=True
        self.trans_alpha=0;self.entering_name=self.maps[dst].name

    def _finish_trans(self):
        dst,tx,ty=self.pending_trans;self.cur_key=dst;self.cur_map=self.maps[dst]
        tx,ty=_arrival_tile(self.cur_map,tx,ty)
        self.player.snap(tx,ty)
        self.pending_trans=None;self.transitioning=False;self.trans_alpha=0
        self.projectiles.clear();self._check_ch();self._cam_snap()
        SoundManager.play_music(self.MAP_MUSIC.get(dst,"village"))
        self.save_game()   # otomatik kayıt: harita geçişi doğal bir kontrol noktası

    # ── Kayıt / Yükleme ─────────────────────────────────────────
    # Haritalar her açılışta üreticilerden yeniden kuruluyor; kayıtta yalnızca
    # oyuncunun DEĞİŞTİRDİĞİ şeyler tutulur: açılan sandıklar ve ölen düşmanlar.
    # Böylece kayıt dosyası küçük kalıyor ve harita içeriği güncellenebiliyor.
    def _cycle_difficulty(self,d):
        i=(DIFF_IDS.index(CFG.data.get("difficulty","normal")) if
           CFG.data.get("difficulty","normal") in DIFF_IDS else 1)
        CFG.data["difficulty"]=DIFF_IDS[(i+d)%len(DIFF_IDS)]

    def _wipe_save(self):
        """Hardcore: ölüm kalıcı. Kayıt siliniyor, dönüş yok."""
        self.permadeath_hit=True
        try:
            if os.path.isfile(SAVE_FILE): os.remove(SAVE_FILE)
        except Exception: pass

    def save_game(self)->bool:
        if not self.player: return False
        if getattr(self,"permadeath_hit",False): return False   # hardcore: öldü, bitti
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
                "equipment":dict(st.equipment),"upgrades":dict(st.upgrades),
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
            st.upgrades={k:int(v) for k,v in pd.get("upgrades",{}).items()
                         if k in EQUIP_ITEMS and 0<int(v)<=UPGRADE_MAX}
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
                if k in self.flags or k.startswith(("kill_","sqpaid_","chests_","boss_")):
                    self.flags[k]=v
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
            # Kayıttan gelen ölüler de zamanla geri doğsun
            for m in self.maps.values():
                for e in m.enemies:
                    if not e.alive and not e.is_boss:
                        e.respawn_at=RESPAWN_FRAMES
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
                        self._hit(e,int(st.attack*1.1),is_crit,self._attack_elem());hit_any=True
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
                    self._hit(e,int(st.magic_atk*0.9),elem=self._attack_elem());hit_any=True
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

    def _attack_elem(self)->str:
        """Temel saldırının elementi: takılı silah belirler, yoksa sınıf."""
        st=self.player.stats
        w=st.equipment.get("weapon")
        return WEAPON_ELEM.get(w) or CLASS_ELEM.get(st.char_class,"physical")

    def _hit(self,e,dmg,crit=False,elem="physical"):
        if crit: dmg=int(dmg*1.8)
        k=elem_mult(elem,getattr(e,"elem","physical"))
        dmg=max(1,int(dmg*k*diff_mult("player_dmg")))
        e.hp-=dmg;e.hp=max(0,e.hp)
        col=UI_GD if crit else HP_R
        # Oyuncu neden az/çok vurduğunu görsün: element etkisi yazıyla söyleniyor
        if k>=1.25:   col=ELEM_COL.get(elem,col); etiket=T_("ui.elem_weak")
        elif k<=0.75: col=(150,150,160);          etiket=T_("ui.elem_resist")
        else:         etiket=T_("ui.crit") if crit else None
        if crit and k>=1.25: etiket=T_("ui.crit")+" "+T_("ui.elem_weak")
        self.hit_fx.append({"x":e.px+TILE//2,"y":e.py+TILE//2,"f":0,"mf":20})
        self.dmg_nums.append({"x":e.px+TILE//2,"y":e.py,"v":dmg,"l":45,"col":col,"txt":etiket})
        self.ps.emit_hit(e.px+TILE//2,e.py+TILE//2)
        SoundManager.play("hit_heavy" if e.is_boss else "hit")
        # Vuruş hissi: kısa donma + krit/boss'ta sarsıntı, kritte geri itme
        self.hit_stop=max(self.hit_stop,5 if crit else 3)
        if crit or e.is_boss: self.add_shake(4 if crit else 2,8)
        if crit: self._knockback(e)
        if e.hp<=0: self._kill(e)

    def _kill(self,e):
        e.alive=False
        # Boss bir daha doğmaz; ötekiler bir süre sonra kendi karesinde.
        e.respawn_at=None if e.is_boss else getattr(self,"tick",0)+RESPAWN_FRAMES
        for item in e.loot:
            if item=="gold": self.player.stats.gold+=5
            elif item in CRYSTAL_FLAG:
                self.player.quest_items.append(item);self._quest_item(item)
            else: self.player.inventory.append(item)
        # Türün malzemesi: avlanmanın asıl geliri ve yükseltmenin yakıtı
        mat=DROP_BY_KIND.get(e.kind)
        if mat and (e.is_boss or random.random()<MAT_DROP_CHANCE):
            self.player.inventory.append(mat)
        lv=self.player.stats.gain_xp(int(e.xp_r*diff_mult("xp")))
        self.player.stats.gold+=int(random.randint(1,4)*diff_mult("gold"))
        self.ps.emit_xp(e.px+TILE//2,e.py+TILE//2);self.ps.emit_gold(e.px+TILE//2,e.py+TILE//2)
        # Yan görev sayacı: her tür için ayrı
        kk="kill_"+e.kind
        self.flags[kk]=self.flags.get(kk,0)+1
        if lv: self.levelup_timer=180; SoundManager.play("level_up")
        if e.is_boss and e.kind=="malachar":
            self.flags["malachar_defeated"]=True
        if e.is_boss and getattr(e,"boss_id",None) in BOSSES:
            self._start_boss_scene(e.boss_id,e.kind)

    def _start_boss_scene(self,boss_id,kind):
        """Ana boss düştü: mühürden bir parça kırılıyor."""
        b=BOSSES[boss_id]
        self.boss_scene={"id":boss_id,"kind":kind,"t":0,"page":0,
                         "lines":list(b["lines"]),"col":b["col"],
                         "name":b["name"],
                         "tohum":zlib.crc32(boss_id.encode("utf-8"))}
        self.flags["boss_"+boss_id]=True
        self.state="boss_scene"
        self.add_shake(7,30)
        SoundManager.play("victory")

    def _end_boss_scene(self):
        """Sahne bitti: Malachar ise kapanışa, değilse oyuna dön."""
        bitti=self.boss_scene["id"]=="malachar"
        self.boss_scene=None
        if bitti:
            self.epi_pages=epilogue_pages(self.flags);self.epi_page=0
            self.state="epilogue"
        else:
            self.state="playing"
            SoundManager.play_music(self.MAP_MUSIC.get(self.cur_key,"village"))

    def _open_shop(self,npc):
        self.shop_npc=npc.name;self.shop_tab=0;self.shop_sel=0;self.shop_msg=None
        self.state="shop";SoundManager.play("open_ui")

    def _shop_rows(self):
        if self.shop_tab==2: return UI.upgrade_rows(self.player)
        return UI.shop_rows(self.player,SHOPS[self.shop_npc],self.shop_tab)

    def _shop_upgrade(self):
        """Seçili parçayı bir kademe yükseltir: altın + malzeme harcar."""
        p=self.player;st=p.stats
        rows=UI.upgrade_rows(p)
        if not(0<=self.shop_sel<len(rows)):
            SoundManager.play("error");return
        k,altin,mal,ok,lvl=rows[self.shop_sel]
        if lvl>=UPGRADE_MAX:
            self.shop_msg=(T_("ui.upg_already_max"),UI_GN);SoundManager.play("error");return
        if not ok:
            eksik="ui.shop_no_gold" if st.gold<altin else "ui.upg_no_material"
            self.shop_msg=(T_(eksik),UI_RD);SoundManager.play("error");return
        # En ucuz malzemeleri harca: değerli olanlar satılığa kalsın
        elde=sorted((x for x in p.inventory if x in MATERIALS),
                    key=lambda x:MATERIALS[x][2])
        for x in elde[:mal]: p.inventory.remove(x)
        st.gold-=altin
        st.upgrades[k]=lvl+1
        self.shop_msg=(T_("ui.upg_done",item_name(k),lvl+1),UI_GN)
        SoundManager.play("level_up")
        self.ps.emit_gold(p.px+TILE//2,p.py)

    def _shop_confirm(self):
        """Seçili satırı al ya da sat."""
        rows=self._shop_rows()
        if not(0<=self.shop_sel<len(rows)):
            SoundManager.play("error");return
        key,price,ok=rows[self.shop_sel]
        st=self.player.stats
        if self.shop_tab==0:
            if not ok:
                reason="ui.shop_no_gold" if st.gold<price else "ui.shop_wrong_class"
                self.shop_msg=(T_(reason),UI_RD);SoundManager.play("error");return
            st.gold-=price;self.player.inventory.append(key)
            self.shop_msg=(T_("ui.shop_bought",item_name(key)),UI_GN)
            SoundManager.play("chest")
        else:
            if key not in self.player.inventory:
                SoundManager.play("error");return
            self.player.inventory.remove(key);st.gold+=price
            self.shop_msg=(T_("ui.shop_sold",item_name(key),price),UI_GD)
            SoundManager.play("equip")
            self.shop_sel=min(self.shop_sel,max(0,len(self._shop_rows())-1))

    def _shop_rest(self):
        st=self.player.stats
        if not SHOPS.get(self.shop_npc,{}).get("rest"): return
        if st.hp>=st.max_hp and st.mp>=st.max_mp:
            self.shop_msg=(T_("ui.shop_rest_full"),GR);SoundManager.play("error");return
        if st.gold<REST_PRICE:
            self.shop_msg=(T_("ui.shop_no_gold"),UI_RD);SoundManager.play("error");return
        st.gold-=REST_PRICE;st.hp=st.max_hp;st.mp=st.max_mp
        self.shop_msg=(T_("ui.shop_rested"),UI_GN);SoundManager.play("heal")

    def _ending_stats(self):
        """Kapanış kartındaki özet: oyuncunun yolculuğu rakamlarla."""
        st=self.player.stats if self.player else None
        if not st: return []
        oldurulen=sum(v for k,v in self.flags.items()
                      if k.startswith("kill_") and isinstance(v,int))
        biten=sum(1 for sq in SIDE_QUESTS if self.flags.get("sqpaid_"+sq["id"]))
        return [(T_("ui.diff_title"),diff_name()),
                (T_("epi.stat_level"),st.level),
                (T_("epi.stat_quests"),"%d/%d"%(biten,len(SIDE_QUESTS))),
                (T_("epi.stat_kills"),oldurulen),
                (T_("epi.stat_chests"),self.flags.get("chests_opened",0)),
                (T_("epi.stat_crystals"),
                 sum(1 for b in ("earth_crystal","water_crystal",
                                 "fire_crystal","light_crystal")
                     if self.flags.get(b))),
                (T_("epi.stat_gold"),st.gold)]

    def _check_side_quests(self):
        """Tamamlanan yan görevin ödülünü bir kez verir."""
        for sq in SIDE_QUESTS:
            paid="sqpaid_"+sq["id"]
            if self.flags.get(paid) or not sq_done(sq,self.flags): continue
            self.flags[paid]=True
            self.player.stats.gold+=int(sq["gold"]*diff_mult("gold"))
            self.player.stats.gain_xp(int(sq["xp"]*diff_mult("xp")))
            SoundManager.play("chest")
            self._toast("%s — %s  (+%d %s, +%d XP)"%(
                T_("ui.sq_done"),T_(sq["title"]),sq["gold"],T_("gold"),sq["xp"]),UI_GD)

    def _quest_item(self,item):
        """Kristal alındı: bayrağı kur, bölümü ilerlet, kalıcı gücü ver."""
        kayit=CRYSTAL_FLAG.get(item)
        if not kayit: return
        bayrak,nitelikler=kayit
        if self.flags.get(bayrak): return
        self.flags[bayrak]=True
        if item=="earth_c": self._advance(4)
        elif item=="water_c": self._advance(6)
        for st_k,v in nitelikler.items():
            self.player.stats.apply_item("stat_"+st_k,v)
        renk={"earth_c":UI_GN,"water_c":UI_CY,
              "fire_c":(250,130,50),"light_c":(250,230,150)}.get(item,UI_GD)
        self.dmg_nums.append({"x":SW//2,"y":SH//2-60,"v":None,"l":130,
                              "col":renk,"txt":item_name(item),"scr":True})

    # ── Yetenek ─────────────────────────────────────────────────
    def _use_ability(self,slot):
        p=self.player;st=p.stats
        if not st.can_use(slot): SoundManager.play("error");return
        ab=ABILITIES[st.char_class][slot];st.mp-=ab["mp"];st.ab_cds[slot]=ab["cd"]
        SoundManager.play("spell")
        cx=p.px+TILE//2;cy=p.py+TILE//2
        d=p.direction;ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d,(0,1))
        aid=ab["id"]
        ae=ABILITY_ELEM.get(aid,"physical")     # yeteneğin elementi
        if aid=="shield_bash":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=1.8:
                    self._hit(e,int(st.attack*1.5),elem=ae)
                    nx2=e.tx+ox;ny2=e.ty+oy
                    if self.cur_map.walkable(nx2,ny2): e.start_step(nx2,ny2,5)
            self.ps.emit_magic(cx,cy,col=(220,120,60))
        elif aid=="whirlwind":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=2.2: self._hit(e,int(st.attack*1.2),elem=ae)
            self.ps.emit(cx,cy,30,(200,150,60),6.0,40)
        elif aid=="war_cry":
            st.buffs["war_cry"]=180;self.ps.emit(cx,cy,25,(220,80,40),5.0,50)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":80,"col":(220,80,40),"txt":T_("ui.shout_war_cry")})
        elif aid=="earthquake":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.attack*2.0),elem=ae)
            for _ in range(40): self.ps.emit(cx+random.randint(-96,96),cy+random.randint(-96,96),5,(180,120,40),3.0,30)
        elif aid=="freeze":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.0:
                    e.frozen=max(e.frozen,120);self._hit(e,int(st.magic_atk*0.8),elem=ae)
            SoundManager.play("freeze")
            self.ps.emit(cx,cy,25,(80,180,255),5.0,50)
        elif aid=="meteor":
            for _ in range(5):
                mx=p.tx+random.randint(-3,3);my=p.ty+random.randint(-3,3)
                for e in self.cur_map.enemies:
                    if e.alive and abs(e.tx-mx)<=1 and abs(e.ty-my)<=1: self._hit(e,int(st.magic_atk*1.8),elem=ae)
                self.ps.emit(mx*TILE+TILE//2,my*TILE+TILE//2,15,(255,80,20),6.0,35)
        elif aid=="arcane_nova":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=4.0: self._hit(e,int(st.magic_atk*2.2),elem=ae)
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
                    p.snap(nx2,ny2);self._hit(e,int(st.attack*2.0),elem=ae)
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
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.magic_atk*1.8),elem=ae)
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
            if pr.owner=="enemy":
                # Menzilli düşmanların mermisi oyuncuyu vurur.
                p=self.player
                if p and p.invincible<=0:
                    prct=pygame.Rect(p.px+4,p.py+4,TILE-8,TILE-8)
                    if prct.collidepoint(pr.x,pr.y):
                        self._player_take_hit(pr.dmg,elem=PROJ_ELEM.get(pr.kind,"physical"));hit=True
            else:
                for e in self.cur_map.enemies:
                    if not e.alive: continue
                    er=pygame.Rect(e.px+2,e.py+2,TILE-4,TILE-4)
                    if er.collidepoint(pr.x,pr.y):
                        self._hit(e,pr.dmg,random.random()<0.08,PROJ_ELEM.get(pr.kind,"physical"))
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
                    self._hit(e,tt.dmg,elem="physical");tt.triggered=True;tt.timer=0
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

    ENEMY_FLEE_DIST = 4      # kaçan düşman bu mesafeye kadar uzaklaşır

    def _enemy_step_to(self,e,tx,ty,spd):
        """Hedef kareye bir adım; dolu ya da duvarsa adım atmaz."""
        if not self.cur_map.walkable(tx,ty): return False
        if any(o.alive and o.tx==tx and o.ty==ty for o in self.cur_map.enemies if o is not e): return False
        if (tx,ty)==(self.player.tx,self.player.ty): return False
        e.start_step(tx,ty,spd);return True

    def _enemy_flee(self,e,spd):
        """Oyuncudan uzaklaşan bir kare dene (önce doğrudan, sonra yanlara)."""
        p=self.player
        dx=(1 if e.tx>p.tx else -1) if e.tx!=p.tx else 0
        dy=(1 if e.ty>p.ty else -1) if e.ty!=p.ty else 0
        for cand in ((e.tx+dx,e.ty+dy),(e.tx+dx,e.ty),(e.tx,e.ty+dy)):
            if cand!=(e.tx,e.ty) and self._enemy_step_to(e,cand[0],cand[1],spd): return True
        return False

    def _pack_mates(self,e,rng):
        return sum(1 for o in self.cur_map.enemies
                   if o.alive and o is not e and o.kind==e.kind
                   and abs(o.tx-e.tx)<=rng and abs(o.ty-e.ty)<=rng)

    def _respawn_tick(self,m):
        """Süresi dolan düşmanları geri getirir.

        Zaman mutlak kare sayısıyla tutuluyor (self.tick): başka haritadayken
        sayaç işlemese de, haritaya dönünce süresi dolmuş olanlar geri gelir.
        Oyuncu yakındaysa beklenir — gözünün önünde belirmesin.
        """
        if not self.player: return
        p=self.player
        for e in m.enemies:
            if e.alive or e.respawn_at is None: continue
            if self.tick < e.respawn_at: continue
            if max(abs(e.home[0]-p.tx),abs(e.home[1]-p.ty)) < RESPAWN_MIN_DIST: continue
            e.diril()

    def _update_enemies(self):
        p=self.player;ppx=p.px+TILE//2;ppy=p.py+TILE//2
        self._respawn_tick(self.cur_map)
        for e in self.cur_map.enemies:
            if not e.alive: continue
            e.advance_step()   # başlamış adımı tamamla (donsa bile kareye otursun)
            if e.frozen>0: e.frozen-=1;continue
            ex=e.px+TILE//2;ey=e.py+TILE//2;dist=math.hypot(ex-ppx,ey-ppy)
            if dist<e.agro_range: e.state="chase"
            elif e.state=="chase" and dist>getattr(e,"leash_range",e.agro_range*1.5):
                e.state="idle"
            if e.state!="chase":
                e.wind_up=0;continue

            bh=behavior(e.kind);btype=bh["type"]
            adjacent=abs(e.tx-p.tx)<=1 and abs(e.ty-p.ty)<=1
            tile_dist=max(abs(e.tx-p.tx),abs(e.ty-p.ty))
            if e.atk_cd>0: e.atk_cd-=1
            if e.shoot_cd>0: e.shoot_cd-=1

            # ── Saldırı telegrafı: önce hazırlanır, sonra vurur ──
            if e.wind_up>0:
                e.wind_up-=1
                if e.wind_up==0:
                    if e.wind_kind=="shoot": self._enemy_shoot(e,bh)
                    elif adjacent: self._enemy_strike(e,p,ppx,ppy)
                    e.atk_cd=self.ENEMY_ATK_CD
                continue   # hazırlanırken yerinden kıpırdamaz

            spd=max(6,20-p.stats.level*2)
            spd=max(3,spd+SPEED_MOD.get(e.kind,0))

            # ── Menzilli: uzaktan atış, yaklaşınca geri çekilme ──
            if btype=="ranged":
                if adjacent and not bh.get("melee_too"):
                    e.move_cd-=1
                    if e.move_cd<=0:
                        e.move_cd=spd;self._enemy_flee(e,spd)
                    continue
                if adjacent and bh.get("melee_too"):
                    if e.atk_cd<=0:
                        e.wind_up=self.ENEMY_WINDUP;e.wind_kind="melee"
                        if e.is_boss: SoundManager.play("boss_alert")
                    continue
                if tile_dist<=bh.get("range",5) and e.shoot_cd<=0:
                    e.wind_up=self.ENEMY_WINDUP;e.wind_kind="shoot"
                    e.shoot_cd=bh.get("cool",90)
                    continue
                # menzil dışındaysa yaklaş
            # ── Ürkek: canı azalınca kaç ────────────────────────
            elif btype=="skittish" and e.hp<=e.max_hp*bh.get("flee_hp",0.3):
                e.move_cd-=1
                if e.move_cd<=0:
                    e.move_cd=max(4,spd-3)
                    if tile_dist<self.ENEMY_FLEE_DIST: self._enemy_flee(e,spd)
                continue
            # ── Sürü: yalnızken çekingen ────────────────────────
            elif btype=="pack" and self._pack_mates(e,bh.get("pack_range",6))==0:
                if adjacent:
                    if e.atk_cd<=0:
                        e.wind_up=self.ENEMY_WINDUP;e.wind_kind="melee"
                    continue
                if tile_dist<=2:
                    e.move_cd-=1
                    if e.move_cd<=0:
                        e.move_cd=spd;self._enemy_flee(e,spd)
                    continue   # yalnız kurt yanaşmaya çekinir

            if adjacent:
                if e.atk_cd<=0:
                    e.wind_up=self.ENEMY_WINDUP;e.wind_kind="melee"
                    if e.is_boss: SoundManager.play("boss_alert")
                continue

            e.move_cd-=1
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
                self._enemy_step_to(e,step[0],step[1],spd)

    def _enemy_shoot(self,e,bh):
        """Menzilli düşman oyuncuya doğru mermi atar."""
        p=self.player
        cx=e.px+TILE//2;cy=e.py+TILE//2
        dx=(p.px+TILE//2)-cx;dy=(p.py+TILE//2)-cy
        mag=math.hypot(dx,dy)
        if mag<=0: return
        pr=Projectile(float(cx),float(cy),dx/mag,dy/mag,4.0,
                      max(1,e.atk-1),bh.get("proj","shadow_bolt"),"enemy")
        self.projectiles.append(pr)
        SoundManager.play("spell")

    ENEMY_WINDUP = 26   # saldırı öncesi hazırlanma (kaçmak için pencere)
    ENEMY_ATK_CD = 14   # iki saldırı arası bekleme
    # 26+14=40 kare: telegraf oncesi ritmin aynisi, ustune kacma penceresi.

    def _player_resist(self,elem)->float:
        """Takılı ekipmanın o elemente karşı koruması (çarpan)."""
        k=1.0
        for ik in self.player.stats.equipment.values():
            r=EQUIP_RESIST.get(ik)
            if r and r[0]==elem: k*=r[1]
        return k

    def _player_take_hit(self,raw,shake=3,elem="physical"):
        """Oyuncuya hasar — yakın dövüş ve düşman mermisi aynı yolu kullanır."""
        p=self.player
        if not p or p.invincible>0: return 0
        dmg=max(1,raw-p.stats.defense+random.randint(-2,3))
        dmg=max(1,int(dmg*self._player_resist(elem)*diff_mult("enemy_dmg")))
        if "holy_shield" in p.stats.buffs:
            sh=p.stats.buffs["holy_shield"]
            if isinstance(sh,int): p.stats.buffs["holy_shield"]=max(0,sh-dmg);dmg=0
        p.stats.hp=max(0,p.stats.hp-dmg);p.invincible=40
        ppx=p.px+TILE//2;ppy=p.py+TILE//2
        self.ps.emit_hit(ppx,ppy)
        self.dmg_nums.append({"x":ppx,"y":ppy-TILE//2,"v":dmg,"l":40,"col":HP_R})
        if dmg>0: self.add_shake(shake,10)
        if p.stats.hp<=0:
            self.state="gameover";SoundManager.play("death")
            if diff_permadeath(): self._wipe_save()
        return dmg

    def _enemy_strike(self,e,p,ppx,ppy):
        """Telegraf tamamlandı: yakın dövüş hasarı uygula."""
        self._player_take_hit(e.atk,shake=5 if e.is_boss else 3,
                              elem=getattr(e,"elem","physical"))

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
                if npc.name in SHOPS: self._open_shop(npc);return
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
                elif ik in CRYSTAL_FLAG: p.quest_items.append(ik);self._quest_item(ik)
                elif ik in("scroll1","scroll2","scroll3"):
                    p.inventory.append(ik)
                    flag_k="sq_"+ik
                    if not self.flags.get(flag_k):
                        self.flags[flag_k]=True;SoundManager.play("spell")
                        self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py-TILE,"v":None,"l":100,"col":UI_PR,"txt":T_("ui.scroll_found")})
                else: p.inventory.append(ik)
            self.cur_map.set(itx,ity,T.FLOOR);self.ps.emit_gold(itx*TILE+TILE//2,ity*TILE+TILE//2);SoundManager.play("chest")
            self.dmg_nums.append({"x":itx*TILE+TILE//2,"y":ity*TILE,"v":None,"l":70,"col":UI_GD,"txt":T_("chest_opened")})
            self.flags["chests_opened"]=self.flags.get("chests_opened",0)+1

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
            reason=p.stats.equip_reason(ik)
            if reason:            # sınıfa uymuyor: eşyaya dokunma, nedenini göster
                SoundManager.play("error")
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py-TILE,"v":None,"l":80,"col":UI_RD,"txt":T_(reason)})
                return
            slot=EQUIP_ITEMS[ik][3]
            SoundManager.play("equip")
            if p.stats.equipment.get(slot)==ik:   # zaten takılı -> çıkar, envantere dön
                p.stats.unequip(slot);p.inventory.append(ik)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_RD,"txt":T_("ui.removed_msg")})
            else:
                old=p.stats.equip(ik);p.inventory.remove(ik)
                if old:           # yuvadaki eski eşya envantere geri dönsün
                    p.inventory.append(old)
                    self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":T_("ui.swapped_msg")})
                else:
                    self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":T_("ui.equipped_msg")})

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
        if self.state=="splash":
            self.splash_t+=1
            # Taç çatladığı anda bir darbe sesi ve hafif sarsıntı
            if self.splash_t==UI.SPLASH_CRACK:
                SoundManager.play("hit_heavy");self.add_shake(5,12)
            if self.splash_t>=UI.SPLASH_END: self.state="title"
        if self.state=="boss_scene" and self.boss_scene:
            self.boss_scene["t"]+=1
            # Silüet dağıldığı anda ağır bir darbe
            if self.boss_scene["t"]==UI.BS_SHATTER:
                SoundManager.play("hit_heavy");self.add_shake(6,20)
            elif self.boss_scene["t"]==UI.BS_CRYSTAL:
                SoundManager.play("chest")
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
                        opts_s=["fullscreen","master_vol","sfx_vol","music_vol","language","show_fps","minimap","difficulty"]
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
                            elif key2=="minimap":   CFG.data["minimap"]=not CFG.data.get("minimap",True)
                            elif key2=="difficulty": self._cycle_difficulty(+1)
                            CFG.save(); SoundManager.play("menu_sel")
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            key2=opts_s[self.settings_sel]
                            if key2=="language": self._cycle_language(-1)
                            elif key2=="difficulty": self._cycle_difficulty(-1)
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
                            self._pause_sel=min(len(UI.pause_opts())-1,self._pause_sel+1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RETURN,pygame.K_e,pygame.K_SPACE):
                            if self._pause_sel==0:   # Devam
                                self.pause_open=False; SoundManager.play("menu_back")
                            elif self._pause_sel==1: # Kaydet
                                ok=self.save_game()
                                self._toast(T_("ui.saved") if ok else T_("ui.save_failed"),UI_GN if ok else UI_RD)
                                SoundManager.play("chest" if ok else "error")
                                self.pause_open=False
                            elif self._pause_sel==2: # Kontroller
                                self.pause_open=False; self.state="tutorial"
                                SoundManager.play("open_ui")
                            elif self._pause_sel==3: # Ayarlar
                                self.settings_open=True; self.settings_sel=0; SoundManager.play("open_ui")
                            elif self._pause_sel==4: # Ana Menü
                                self._reset(); SoundManager.play("menu_back")
                            elif self._pause_sel==5: # Çıkış
                                running=False
                        elif k==pygame.K_ESCAPE:
                            self.pause_open=False; SoundManager.play("menu_back")
                        continue

                    # ── State'e göre input ──
                    if self.state=="tutorial":
                        # Herhangi bir tuş kapatır; bir daha açılmaz.
                        if k not in(pygame.K_F11,pygame.K_F1):
                            CFG.data["tutorial_seen"]=True; CFG.save()
                            self.state="playing"; SoundManager.play("menu_sel")

                    elif self.state=="splash":
                        self.state="title";SoundManager.play("menu_back")

                    elif self.state=="difficulty_select":
                        if k in(pygame.K_UP,pygame.K_w):
                            self.diff_sel=max(0,self.diff_sel-1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_DOWN,pygame.K_s):
                            self.diff_sel=min(len(DIFFICULTIES)-1,self.diff_sel+1); SoundManager.play("menu_sel")
                        elif k in(pygame.K_RETURN,pygame.K_e,pygame.K_SPACE):
                            CFG.data["difficulty"]=DIFF_IDS[self.diff_sel]; CFG.save()
                            self.state="stat_alloc"; SoundManager.play("menu_sel")
                        elif k==pygame.K_ESCAPE:
                            self.state="class_select"; SoundManager.play("menu_back")

                    elif self.state=="title":
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
                            self.temp_stats=PlayerStats(ks[self.class_sel]); self.free_pts=10; self.stat_sel=0; self.is_lu=False
                            self.state="difficulty_select"; SoundManager.play("menu_sel")
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

                    elif self.state=="shop":
                        rows=self._shop_rows()
                        if k==pygame.K_TAB:
                            n_tab=len(UI.shop_tabs(SHOPS[self.shop_npc]))
                            self.shop_tab=(self.shop_tab+1)%n_tab
                            self.shop_sel=0;self.shop_msg=None
                            SoundManager.play("menu_sel")
                        elif k in(pygame.K_UP,pygame.K_w):
                            self.shop_sel=max(0,self.shop_sel-1);SoundManager.play("menu_sel")
                        elif k in(pygame.K_DOWN,pygame.K_s):
                            self.shop_sel=min(max(0,len(rows)-1),self.shop_sel+1);SoundManager.play("menu_sel")
                        elif k in(pygame.K_e,pygame.K_RETURN):
                            if self.shop_tab==2: self._shop_upgrade()
                            else: self._shop_confirm()
                        elif k==pygame.K_r: self._shop_rest()
                        elif k==pygame.K_ESCAPE:
                            self.state="playing";self.shop_msg=None;SoundManager.play("menu_back")

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

                    elif self.state=="boss_scene":
                        if self.boss_scene is None:
                            self.state="playing"
                        elif self.boss_scene["t"]<UI.BS_TEXT:
                            # Animasyonu geç
                            self.boss_scene["t"]=UI.BS_TEXT
                        elif k in(pygame.K_RETURN,pygame.K_SPACE,pygame.K_e):
                            self.boss_scene["page"]+=1
                            SoundManager.play("menu_sel")
                            if self.boss_scene["page"]>=len(self.boss_scene["lines"]):
                                self._end_boss_scene()
                        elif k==pygame.K_ESCAPE:
                            self._end_boss_scene()

                    elif self.state=="epilogue":
                        if k in(pygame.K_RETURN,pygame.K_SPACE,pygame.K_e):
                            self.epi_page+=1
                            SoundManager.play("menu_sel")
                            if self.epi_page>=len(self.epi_pages): self.state="victory"
                        elif k==pygame.K_ESCAPE:
                            self.state="victory"

                    elif self.state=="victory":
                        if k in(pygame.K_ESCAPE,pygame.K_RETURN): self._reset()

                    elif self.state=="playing":
                        if k==pygame.K_ESCAPE:
                            self.pause_open=True; self._pause_sel=0; SoundManager.play("open_ui")
                        elif k==pygame.K_F1:
                            self.settings_open=True; self.settings_sel=0; SoundManager.play("open_ui")
                        elif k==pygame.K_i:
                            self.inv_sel=0; self.inv_tab=0; self.state="inventory"; SoundManager.play("open_ui")
                        elif k==pygame.K_m:      # mini haritayı aç/kapat
                            CFG.data["minimap"]=not CFG.data.get("minimap",True)
                            CFG.save(); SoundManager.play("menu_sel")
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
            if self.state=="splash": self.ui.draw_splash(self.screen,self.splash_t,self.tick)
            elif self.state=="title": self.ui.draw_title(self.screen,self.tick)
            elif self.state=="story": self.ui.draw_story(self.screen,self.story_shown,self.tick)
            elif self.state=="class_select": self.ui.draw_class_select(self.screen,self.class_sel,self.tick)
            elif self.state=="difficulty_select": self.ui.draw_difficulty(self.screen,self.diff_sel,self.tick)
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
                        elif _n.name in SHOPS:
                            self.ui.draw_shop_marker(self.screen,_n.tx,_n.ty,
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
                elif self.state=="shop":
                    self.ui.draw_shop(self.screen,self.player,SHOPS[self.shop_npc],
                                      self.shop_npc,self.shop_tab,self.shop_sel,
                                      self.tick,self.shop_msg)
                elif self.state=="quest_log":
                    self.ui.draw_quest_log(self.screen,self.flags,self.flags["ch"])
                elif self.state=="tutorial":
                    self.ui.draw_tutorial(self.screen,self.tick)
                elif self.state=="levelup_alloc":
                    self.ui.draw_stat_alloc(self.screen,self.player.stats,self.player.stats.skill_points,self.stat_sel,True,self.tick)
                elif self.state=="gameover":
                    self.ui.draw_gameover(self.screen)
                elif self.state=="boss_scene" and self.boss_scene:
                    self.ui.draw_boss_scene(self.screen,self.boss_scene,self.tick)
                elif self.state=="epilogue":
                    sf=self.epi_pages[min(self.epi_page,len(self.epi_pages)-1)]
                    self.ui.draw_epilogue(self.screen,sf,self.epi_page,len(self.epi_pages),self.tick)
                elif self.state=="victory":
                    self.ui.draw_victory(self.screen,self.tick,self._ending_stats(),
                                         ending_rank(self.flags))

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
                if CFG.minimap:
                    self.ui.draw_minimap(self.screen,self.cur_map,self.player,self.tick)
                self.ui.draw_mini_quests(self.screen,self.flags,self.player.stats.char_class)
            pygame.display.flip()

        pygame.quit();sys.exit()


if __name__=="__main__":
    print("="*56)
    print(f"  KARANLIK TAC'IN LANETI  v{VERSION}")
    print("  pip install pygame  |  python pixel_rpg.py")
    print("  Yeni: Sinifa ozgun saldiri | Ekipman Sistemi")
    print("  Yeni: Gorunmez harita gecisleri | Genis orman")
    print(f"  Ayarlar: {SETTINGS_FILE}")
    print("="*56)
    Game().run()
