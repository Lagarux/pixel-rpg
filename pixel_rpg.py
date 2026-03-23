#!/usr/bin/env python3
"""
KARANLIK TAC'IN LANETI  v4.0  ─  2D Pixel RPG
pip install pygame  |  python pixel_rpg.py

Kontroller:
  WASD / Ok Tuslari  ->  Hareket
  E                  ->  Konus / Etkilesim / Onayla
  Space              ->  Sinifa ozel saldiri
  1 2 3 4            ->  Yetenek kullan
  I                  ->  Envanter / Ekipman
  Q                  ->  Gorev Gunlugu
  U                  ->  Nitelik dagitimi
  R  (game over)     ->  Yeniden basla
"""

import ctypes

# Windows'un bu pencereyi ayrı bir uygulama gibi gruplamasını sağlar
try:
    myappid = 'PixelRPG.1.0' # Buraya istediğin benzersiz bir yazı yazabilirsin
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass



import pygame, sys, math, random
from collections import deque
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass

# İkon resmini belleğe yükle (32x32 boyutlarında olması önerilir)
icon_image = pygame.image.load("icon.png")
# Yüklenen resmi ikon olarak ayarla
pygame.display.set_icon(icon_image)

# Pencere oluşturuluyor...
# screen = pygame.display.set_mode((SW, SH))


SW, SH = 960, 640
TILE    = 32
FPS     = 60
TITLE   = "Karanlık Tacın Laneti"

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
    # Aksesuarlar
    "power_ring":   ("Guc Yuzugu",   UI_GD,  {"str":2,"vit":1},  "ring",      None),
    "mana_gem":     ("Mana Tası",    UI_CY,  {"wis":2,"int":1},  "ring",      None),
    "swift_boots":  ("Hiz Botları",  G_L,    {"agi":3},          "ring",      None),
    "warrior_crest":("Savasci Nisan",(220,80,40),{"str":2,"vit":2},"ring",    {"warrior"}),
    "mage_focus":   ("Odak Kristali",UI_AC,  {"int":3,"wis":1},  "ring",      {"mage"}),
    "archer_token": ("Nisan Tası",   G_L,    {"agi":2,"str":1},  "ring",      {"archer"}),
}

ITEMS = {
    "hp_pot": ("Saglik Iksiri", HP_G,   "heal",   35,  "35 HP iyilestirir."),
    "mp_pot": ("Mana Iksiri",   MP_B,   "mana",   25,  "25 MP iyilestirir."),
    "gold":   ("Altin",         UI_GD,  "gold",    5,  "Degerli para."),
    "earth_c":("Toprak Kristali",(120,200,80),"quest",0,"Antik kristal."),
    "water_c":("Su Kristali",  (80,180,220),"quest",0,"Antik kristal."),
    "farm_tool":("Ciftci Aleti",(140,100,60),"stat_str",1,"STR +1 kalici."),
    "river_gem":("Nehir Tasi", (60,180,200),"stat_wis",1,"WIS +1 kalici."),
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

    @staticmethod
    def player_surf(direction,frame,char_class="warrior"):
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        bob=int(math.sin(frame*0.3)*1.5)
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
        lo=int(math.sin(frame*0.4)*3)
        lc=(int(cc[0]*0.7),int(cc[1]*0.7),int(cc[2]*0.7))
        pygame.draw.rect(s,lc,(10,26+bob,5,6-abs(lo)//2));pygame.draw.rect(s,lc,(17,26+bob,5,6+abs(lo)//2))
        pygame.draw.rect(s,(35,25,18),(9,31+bob,6,2));pygame.draw.rect(s,(35,25,18),(16,31+bob,6,2))
        sw=int(math.sin(frame*0.4)*2)
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
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        bob=int(math.sin(frame*0.2)*1);skin=(200,160,120)
        if style=="guard":
            pygame.draw.rect(s,(80,90,110),(9,13+bob,14,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.rect(s,(60,70,90),(7,2+bob,18,6))
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
            pygame.draw.line(s,ST_L,(24,8+bob),(24,26+bob),2)
        elif style=="elder":
            pygame.draw.rect(s,(130,100,160),(8,13+bob,16,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.polygon(s,(80,40,120),[(16,bob-2),(8,6+bob),(24,6+bob)])
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
            pygame.draw.rect(s,WOD,(25,5+bob,3,24));pygame.draw.circle(s,(180,100,255),(26,5+bob),4)
        elif style=="knight":
            pygame.draw.rect(s,(80,80,100),(9,13+bob,14,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.rect(s,(70,70,90),(7,2+bob,18,7))
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
        elif style=="oracle":
            pygame.draw.rect(s,(60,40,100),(8,13+bob,16,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.polygon(s,(40,20,80),[(16,bob-4),(7,7+bob),(25,7+bob)])
            pygame.draw.circle(s,UI_GD,(16,bob-2),3)
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
            for i in range(3):
                ang=frame*0.05+i*2.1;ex=int(16+8*math.cos(ang));ey=int(16+5*math.sin(ang)+bob)
                if 0<=ex<TILE and 0<=ey<TILE: pygame.draw.circle(s,UI_GD,(ex,ey),1)
        elif style=="farmer":
            pygame.draw.rect(s,(140,100,60),(8,13+bob,16,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.rect(s,(100,80,40),(7,3+bob,18,5))
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
            pygame.draw.rect(s,WOD,(24,10+bob,3,18))
        else:
            pygame.draw.rect(s,color,(8,13+bob,16,14));pygame.draw.rect(s,skin,(9,3+bob,14,12))
            pygame.draw.rect(s,BK,(11,7+bob,3,3));pygame.draw.rect(s,BK,(18,7+bob,3,3))
        return s

    @staticmethod
    def enemy_surf(kind,frame):
        s=pygame.Surface((TILE,TILE),pygame.SRCALPHA)
        bob=int(math.sin(frame*0.25)*2)
        if kind=="slime":
            pygame.draw.ellipse(s,(55,175,55),(4,14+bob,24,16));pygame.draw.ellipse(s,(75,205,75),(6,12+bob,20,14))
            pygame.draw.circle(s,BK,(11,17+bob),3);pygame.draw.circle(s,BK,(21,17+bob),3)
            pygame.draw.circle(s,WH,(12,16+bob),1);pygame.draw.circle(s,WH,(22,16+bob),1)
        elif kind=="skeleton":
            for y in range(14,26,4): pygame.draw.line(s,WH,(12,y+bob),(20,y+bob),2)
            pygame.draw.rect(s,WH,(9,3+bob,14,12));pygame.draw.rect(s,BK,(10,6+bob,4,4));pygame.draw.rect(s,BK,(18,6+bob,4,4))
            pygame.draw.rect(s,HP_R,(11,7+bob,2,2));pygame.draw.rect(s,HP_R,(19,7+bob,2,2))
            for tx in range(11,21,3): pygame.draw.rect(s,WH,(tx,13+bob,2,3))
            lo=int(math.sin(frame*0.3)*4)
            pygame.draw.line(s,WH,(12,26+bob),(10,32+bob+lo),2);pygame.draw.line(s,WH,(20,26+bob),(22,32+bob-lo),2)
            pygame.draw.line(s,ST_L,(28,14+bob),(28,26+bob),2);pygame.draw.line(s,UI_GD,(25,16+bob),(31,16+bob),2)
        elif kind=="goblin":
            pygame.draw.rect(s,(78,138,58),(9,16+bob,14,12));pygame.draw.ellipse(s,(98,158,68),(7,4+bob,18,14))
            pygame.draw.ellipse(s,(78,128,48),(2,6+bob,8,5));pygame.draw.ellipse(s,(78,128,48),(22,6+bob,8,5))
            pygame.draw.circle(s,(218,48,48),(11,9+bob),3);pygame.draw.circle(s,(218,48,48),(21,9+bob),3)
            pygame.draw.circle(s,BK,(12,9+bob),1);pygame.draw.circle(s,BK,(22,9+bob),1)
            pygame.draw.rect(s,WOD,(24,14+bob,4,14))
        elif kind=="wolf":
            pygame.draw.ellipse(s,(90,80,70),(4,14+bob,24,14));pygame.draw.ellipse(s,(100,90,80),(6,8+bob,16,12))
            pygame.draw.polygon(s,(80,70,60),[(8,8+bob),(6,2+bob),(11,6+bob)])
            pygame.draw.polygon(s,(80,70,60),[(20,8+bob),(22,2+bob),(17,6+bob)])
            pygame.draw.circle(s,(220,180,30),(10,11+bob),2);pygame.draw.circle(s,(220,180,30),(18,11+bob),2)
            pygame.draw.circle(s,BK,(10,11+bob),1);pygame.draw.circle(s,BK,(18,11+bob),1)
            lo=int(math.sin(frame*0.4)*3)
            for lx in [6,12,18,24]: pygame.draw.rect(s,(80,70,60),(lx,26+bob,4,6+abs(lo)//2))
        elif kind=="boar":
            pygame.draw.ellipse(s,(130,80,60),(4,14+bob,24,14));pygame.draw.ellipse(s,(140,90,70),(5,8+bob,14,12))
            pygame.draw.polygon(s,(120,70,50),[(5,8+bob),(3,4+bob),(8,6+bob)])
            pygame.draw.circle(s,(220,60,60),(9,11+bob),2);pygame.draw.circle(s,(220,60,60),(15,11+bob),2)
            pygame.draw.polygon(s,WH,[(4,13+bob),(2,9+bob),(6,10+bob)])
            for lx in [6,10,16,22]: pygame.draw.rect(s,(110,65,45),(lx,26+bob,4,6))
        elif kind=="golem":
            pygame.draw.rect(s,(75,70,65),(5,8+bob,22,22));pygame.draw.rect(s,(95,90,85),(6,9+bob,20,20))
            glow=int(abs(math.sin(frame*0.1))*100)+100
            pygame.draw.circle(s,(glow,80,30),(11,13+bob),4);pygame.draw.circle(s,(glow,80,30),(21,13+bob),4)
            pygame.draw.circle(s,(255,180,80),(11,13+bob),2);pygame.draw.circle(s,(255,180,80),(21,13+bob),2)
        elif kind=="scorpion":
            pygame.draw.ellipse(s,(160,100,50),(6,12+bob,20,14));pygame.draw.ellipse(s,(180,120,60),(8,13+bob,16,10))
            pygame.draw.line(s,(150,90,40),(6,16+bob),(2,12+bob),2);pygame.draw.line(s,(150,90,40),(26,16+bob),(30,12+bob),2)
            pygame.draw.circle(s,(150,90,40),(2,11+bob),3);pygame.draw.circle(s,(150,90,40),(30,11+bob),3)
            pygame.draw.circle(s,HP_R,(24,1+bob),3)
            pygame.draw.circle(s,(220,50,50),(11,14+bob),2);pygame.draw.circle(s,(220,50,50),(21,14+bob),2)
        elif kind=="ice_wolf":
            pygame.draw.ellipse(s,(130,180,220),(4,14+bob,24,14));pygame.draw.ellipse(s,(150,200,235),(6,8+bob,16,12))
            pygame.draw.polygon(s,(120,170,210),[(8,8+bob),(6,2+bob),(11,6+bob)])
            pygame.draw.polygon(s,(120,170,210),[(20,8+bob),(22,2+bob),(17,6+bob)])
            pygame.draw.circle(s,(180,240,255),(10,11+bob),2);pygame.draw.circle(s,(180,240,255),(18,11+bob),2)
            pygame.draw.circle(s,BK,(10,11+bob),1);pygame.draw.circle(s,BK,(18,11+bob),1)
            lo=int(math.sin(frame*0.4)*3)
            for lx in [6,12,18,24]: pygame.draw.rect(s,(120,170,210),(lx,26+bob,4,6+abs(lo)//2))
        elif kind=="shadow_knight":
            pygame.draw.rect(s,(40,20,65),(8,12+bob,16,16));pygame.draw.rect(s,(55,30,85),(9,13+bob,14,14))
            pygame.draw.rect(s,(40,20,65),(7,3+bob,18,12));pygame.draw.rect(s,(55,30,85),(8,4+bob,16,10))
            pygame.draw.rect(s,BK,(9,8+bob,14,4))
            glow2=int(abs(math.sin(frame*0.08))*150)+80
            pygame.draw.rect(s,(glow2,0,glow2//2),(9,8+bob,14,4))
            pygame.draw.rect(s,(60,35,90),(26,10+bob,3,18));pygame.draw.rect(s,(120,50,160),(24,12+bob,7,2))
            aa=int(abs(math.sin(frame*0.06))*50)+20
            asurf=pygame.Surface((TILE,TILE),pygame.SRCALPHA);pygame.draw.circle(asurf,(100,0,150,aa),(16,16),15);s.blit(asurf,(0,0))
        elif kind=="malachar":
            sc=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA);b2=int(math.sin(frame*0.15)*3)
            pygame.draw.rect(sc,(25,10,45),(12,22+b2,40,42));pygame.draw.rect(sc,(35,15,60),(14,24+b2,36,40))
            pygame.draw.rect(sc,(20,8,38),(16,18+b2,32,26));pygame.draw.ellipse(sc,(20,8,38),(14,4+b2,36,22))
            pygame.draw.polygon(sc,(60,20,80),[(20,6+b2),(14,b2-4),(18,10+b2)])
            pygame.draw.polygon(sc,(60,20,80),[(44,6+b2),(50,b2-4),(46,10+b2)])
            gm=int(abs(math.sin(frame*0.06))*180)+60
            pygame.draw.circle(sc,(gm,0,gm//2),(22,14+b2),5);pygame.draw.circle(sc,(gm,0,gm//2),(42,14+b2),5)
            pygame.draw.circle(sc,(255,150,200),(22,14+b2),2);pygame.draw.circle(sc,(255,150,200),(42,14+b2),2)
            pygame.draw.rect(sc,(50,20,75),(15,3+b2,34,6))
            for ti in range(0,34,6): pygame.draw.polygon(sc,UI_BD,[(16+ti,3+b2),(19+ti,-2+b2),(22+ti,3+b2)])
            aa2=int(abs(math.sin(frame*0.05))*80)+30
            as2=pygame.Surface((TILE*2,TILE*2),pygame.SRCALPHA);pygame.draw.circle(as2,(120,0,180,aa2),(32,32),30);sc.blit(as2,(0,0))
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
class Entity:
    def __init__(self,tx,ty):
        self.tx=tx;self.ty=ty;self.px=tx*TILE;self.py=ty*TILE;self.direction="down";self.frame=0

class Player(Entity):
    def __init__(self,tx,ty,stats):
        super().__init__(tx,ty);self.stats=stats
        self.inventory:List[str]=["hp_pot"]
        self.quest_items:List[str]=[]
        self.invincible=0;self.attacking=False;self.atk_frame=0;self.atk_max=15
    def draw(self,surf,cx,cy):
        if self.invincible>0 and (self.invincible//4)%2==1: return
        surf.blit(PA.player_surf(self.direction,self.frame,self.stats.char_class),(self.px-cx,self.py-cy))

class NPC(Entity):
    def __init__(self,tx,ty,name,color,dialog_fn,style="default"):
        super().__init__(tx,ty);self.name=name;self.color=color;self.dialog_fn=dialog_fn;self.style=style
    def get_dialog(self,flags): return self.dialog_fn(flags)
    def draw(self,surf,cx,cy):
        surf.blit(PA.npc_surf(self.color,self.frame,self.style),(self.px-cx,self.py-cy))
        fnt=pygame.font.SysFont("monospace",9,bold=True);tag=fnt.render(self.name,True,WH)
        tx2=self.px-cx+TILE//2-tag.get_width()//2;ty2=self.py-cy-14
        bg=pygame.Surface((tag.get_width()+4,tag.get_height()+2),pygame.SRCALPHA)
        bg.fill((0,0,0,160));surf.blit(bg,(tx2-2,ty2-1));surf.blit(tag,(tx2,ty2))

class Enemy(Entity):
    def __init__(self,tx,ty,kind,hp,atk,xp,agro=5,loot=None,is_boss=False):
        super().__init__(tx,ty)
        self.kind=kind;self.max_hp=hp;self.hp=hp;self.atk=atk;self.xp_r=xp
        self.agro_range=agro*TILE;self.loot=loot or [];self.is_boss=is_boss
        self.alive=True;self.state="idle";self.move_cd=0;self.frozen=0
    def draw(self,surf,cx,cy):
        if not self.alive: return
        sp=PA.enemy_surf(self.kind,self.frame);bx=self.px-cx;by=self.py-cy
        if self.kind=="malachar": surf.blit(sp,(bx-TILE//2,by-TILE//2))
        else: surf.blit(sp,(bx,by))
        if self.frozen>0:
            fs=pygame.Surface((TILE,TILE),pygame.SRCALPHA);fs.fill((100,180,255,80));surf.blit(fs,(bx,by))
        bw=56 if self.is_boss else 28;bh=5 if self.is_boss else 4
        bbx=bx+(TILE-bw)//2;bby=by+(-14 if self.is_boss else -8)
        pygame.draw.rect(surf,HP_R,(bbx,bby,bw,bh))
        pygame.draw.rect(surf,HP_G,(bbx,bby,int(bw*max(0,self.hp)/self.max_hp),bh))
        pygame.draw.rect(surf,BK,(bbx,bby,bw,bh),1)
        if self.is_boss:
            fnt=pygame.font.SysFont("monospace",9,bold=True)
            tt=fnt.render(f"{self.kind.upper()} {self.hp}/{self.max_hp}",True,UI_TX)
            surf.blit(tt,(bbx+bw//2-tt.get_width()//2,bby-12))

# ─── GameMap ────────────────────────────────────────────────────
class GameMap:
    def __init__(self,w,h,name,ambient=(0,0,0)):
        self.w=w;self.h=h;self.name=name;self.ambient=ambient
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
            ao=pygame.Surface((SW,SH),pygame.SRCALPHA);ao.fill((*self.ambient,55));surf.blit(ao,(0,0))
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

def _snap_all(m):
    occ=set()
    for e in m.npcs+m.enemies:
        tx,ty=_snap(m,e.tx,e.ty);att=0
        while(tx,ty) in occ and att<30:
            tx2,ty2=_snap(m,tx+(att%5)-2,ty+(att//5)-2)
            if(tx2,ty2) not in occ: tx,ty=tx2,ty2;break
            att+=1
        e.tx=tx;e.ty=ty;e.px=tx*TILE;e.py=ty*TILE;occ.add((tx,ty))

def _add_trans(m,tiles,dst,dtx,dty,ground=T.GRASS,hint_dir=(1,0)):
    """Geçiş ekle — tile normal zemin olur, görsel ok gösterilir."""
    for tx,ty in tiles:
        m.set(tx,ty,ground)
        m.transitions[(tx,ty)]=(dst,dtx,dty)
        m.trans_hints[(tx,ty)]=(hint_dir[0],hint_dir[1],dst)

# ─── Haritalar ───────────────────────────────────────────────────
def build_ashveil():
    m = GameMap(60, 50, "Ashveil Koyu")
    _rect(m, 0, 0, 60, 50, T.GRASS)
    # Göl
    for ty in range(3, 12):
        for tx in range(2, 14):
            if (tx-7)**2 + (ty-7)**2 < 20: m.set(tx, ty, T.WATER)
    for ty in range(2, 13):
        for tx in range(1, 16):
            if m.get(tx,ty)==T.GRASS:
                if any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.SAND)
    # Ana yollar
    _path(m, 2, 23, 58, 23, T.STONE, 2)
    _path(m, 29, 2, 29, 48, T.STONE, 2)
    # Evler (yol bağlantılı)
    _room(m, 15,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 33,  7, 10, 8, T.WALL, T.FLOOR, "south")
    _room(m, 15, 28, 10, 8, T.WALL, T.FLOOR, "north")
    _room(m, 33, 28, 10, 8, T.WALL, T.FLOOR, "north")
    # Ev-yol bağlantıları
    _path(m, 19, 15, 19, 23, T.STONE, 2)
    _path(m, 37, 15, 37, 23, T.STONE, 2)
    _path(m, 19, 28, 19, 23, T.STONE, 2)
    _path(m, 37, 28, 37, 23, T.STONE, 2)
    # Sandıklar ev içinde
    m.set(17, 10, T.CHEST); m.chests[(17,10)] = ["hp_pot","gold"]
    m.set(35, 10, T.CHEST); m.chests[(35,10)] = ["mp_pot","iron_sword"]
    m.set(17, 30, T.CHEST); m.chests[(17,30)] = ["leather_armor","gold"]
    # Sabit orman koridoru (sağ, y=19..27 tamamen açık)
    for ty in range(0, 50):
        for tx in range(42, 60):
            if 19 <= ty <= 27:
                m.set(tx, ty, T.GRASS)
            else:
                col = (tx-42) % 4; row = ty % 4
                if col < 2 and row < 2: m.set(tx, ty, T.TREE)
    for tx in range(38, 60):
        m.set(tx, 22, T.STONE); m.set(tx, 23, T.STONE)
    for ty in range(19, 28):
        for tx in range(38, 60):
            if m.get(tx,ty) == T.TREE: m.set(tx,ty,T.GRASS)
    # Sınır ağaçları (geçişlerden ÖNCE)
    for tx in range(0, 60): m.set(tx,0,T.TREE); m.set(tx,1,T.TREE)
    for ty in range(0, 50): m.set(0,ty,T.TREE); m.set(1,ty,T.TREE)
    # Geçişler (x=2,3'ten başlıyor, sınır ağacının üstüne yazılmıyor)
    _add_trans(m, [(58,ty) for ty in range(20,27)]+[(59,ty) for ty in range(20,27)],
               "dark_forest", 3, 22, T.GRASS, (1,0))
    _add_trans(m, [(tx,48) for tx in range(20,32)]+[(tx,49) for tx in range(20,32)],
               "south_meadow", 20, 3, T.GRASS, (0,1))
    _add_trans(m, [(2,ty) for ty in range(20,29)]+[(3,ty) for ty in range(20,29)],
               "west_river", 52, 22, T.GRASS, (-1,0))
    _add_trans(m, [(27,46),(28,46),(29,46),(30,46),(27,47),(28,47),(29,47),(30,47)],
               "village_dungeon", 18, 3, T.DIRT, (0,1))
    # NPCler
    def aldric_d(f):
        if f.get("ch",1)>=6: return ["Kahraman! Krallik sana borclu."]
        if f.get("water_crystal"): return ["Su kristali bulundu!","Golge Kalesine git."]
        if f.get("earth_crystal"): return ["Bir kristal bulundu!","Col Yoluna git, Oracle Nyx seni bekliyor."]
        return ["Ah genc kahraman! Sonunda geldin.","Malachar'in muhuru cozuluyor.",
                "Dort Kutsal Kristali bulmalısin.","Doğudaki Karanlik Ormandan basla.","[ Gorev Guncellendi! ]"]
    m.npcs.append(NPC(22, 19, "Yasli Aldric", (160,100,60), aldric_d, "elder"))
    def smith_d(f): return ["Iyi silahlar icin altin getir.","Sandıklardan ekipman bulabilirsin.","[I] ile ekipmanı giyin!"]
    m.npcs.append(NPC(17, 13, "Demirci Boran", (140,90,50), smith_d, "guard"))
    def inn_d(f): return ["Konaklamak ister misin?","Bol sans!"]
    m.npcs.append(NPC(37, 13, "Hanci Mira", (180,130,160), inn_d))
    def guard_d(f):
        if not f.get("speak_aldric"): return ["Dur! Once Yasli Aldric'i gor."]
        return ["Gecebilirsin.","Doğuda Karanlik Orman var."]
    m.npcs.append(NPC(54, 19, "Koy Muhafizi", (100,120,180), guard_d, "guard"))
    def south_d(f): return ["Guneyde guzel cayirlar var."]
    m.npcs.append(NPC(22, 45, "Yolcu", (160,180,140), south_d))
    def west_d(f): return ["Batida nehir ve kopru var.","Balikci Riva orada yasiyor."]
    m.npcs.append(NPC(6, 25, "Koy Yerlisi", (140,160,180), west_d))
    m.enemies += [
        Enemy(46,10,"slime",20,4,12,agro=4,loot=["gold"]),
        Enemy(50, 8,"slime",20,4,12,agro=4),
        Enemy(54,14,"goblin",35,7,22,agro=5,loot=["hp_pot"]),
    ]
    _snap_all(m); return m


def build_dark_forest():
    """Sabit orman tasarımı."""
    m = GameMap(56, 44, "Karanlik Orman", ambient=(0,20,0))
    _rect(m, 0, 0, 56, 44, T.GRASS)
    # Kenar ağaçları
    for ty in range(44):
        m.set(0,ty,T.DARK_TREE); m.set(1,ty,T.DARK_TREE)
        m.set(54,ty,T.DARK_TREE); m.set(55,ty,T.DARK_TREE)
    for tx in range(56):
        m.set(tx,0,T.DARK_TREE); m.set(tx,1,T.DARK_TREE)
        m.set(tx,42,T.DARK_TREE); m.set(tx,43,T.DARK_TREE)
    # Sabit ağaç grupları (köşelerde, merkezden uzak)
    for tx,ty in [
        (4,4),(5,4),(6,4),(4,5),(5,5),(4,6),(8,4),(9,4),(10,4),(8,5),(9,5),
        (4,8),(5,8),(4,9),(5,9),(4,10),(8,8),(9,8),(10,8),(8,9),(9,9),
        (42,4),(43,4),(44,4),(42,5),(43,5),(46,4),(47,4),(48,4),(46,5),(47,5),
        (42,8),(43,8),(44,8),(42,9),(43,9),(46,8),(47,8),(48,8),(46,9),(47,9),
        (4,30),(5,30),(6,30),(4,31),(5,31),(8,30),(9,30),(10,30),(8,31),(9,31),
        (4,34),(5,34),(4,35),(5,35),(8,34),(9,34),(10,34),(8,35),(9,35),
        (42,30),(43,30),(44,30),(42,31),(43,31),(46,30),(47,30),(48,30),
        (42,34),(43,34),(44,34),(42,35),(43,35),(46,34),(47,34),(48,34),
    ]: m.set(tx,ty,T.DARK_TREE)
    # Ana yollar (tamamen temiz)
    for ty in range(17,26):
        for tx in range(56):
            if m.get(tx,ty)==T.DARK_TREE: m.set(tx,ty,T.GRASS)
    _path(m, 0, 21, 56, 21, T.DIRT, 2)
    for ty in range(44):
        for tx in range(24,32):
            if m.get(tx,ty)==T.DARK_TREE: m.set(tx,ty,T.GRASS)
    _path(m, 27, 0, 27, 44, T.DIRT, 2)
    # Geçişler
    _add_trans(m, [(2,ty) for ty in range(18,26)]+[(3,ty) for ty in range(18,26)],
               "ashveil", 57, 23, T.GRASS, (-1,0))
    _add_trans(m, [(tx,2) for tx in range(24,32)]+[(tx,3) for tx in range(24,32)],
               "ruins", 16, 44, T.GRASS, (0,-1))
    # Sandıklar (açık alanlarda)
    m.set(16, 14, T.CHEST); m.chests[(16,14)] = ["hp_pot","fine_bow"]
    m.set(38, 14, T.CHEST); m.chests[(38,14)] = ["mp_pot","power_ring"]
    m.set(16, 28, T.CHEST); m.chests[(16,28)] = ["leather_armor","gold"]
    def roland_d(f):
        if f.get("ch",1)>=3: return ["Iyi is cikardin. Harabeler seni bekliyor."]
        return ["Ugh... Saldiriya ugradim.","Harabelerde Toprak Kristali var.",
                "Kuzeye git!","Dikkat et — Taş Golem orayi koruyor!","[ Gorev Guncellendi! ]"]
    m.npcs.append(NPC(20, 21, "Sir Roland", (130,160,130), roland_d, "knight"))
    m.enemies += [
        Enemy(16,12,"wolf",35,8,20,agro=5,loot=["gold"]),
        Enemy(36,12,"wolf",35,8,20,agro=5),
        Enemy(40,18,"goblin",40,9,25,agro=5,loot=["hp_pot"]),
        Enemy(16,30,"skeleton",50,11,32,agro=6,loot=["mp_pot"]),
        Enemy(38,30,"goblin",45,10,28,agro=6,loot=["gold"]),
        Enemy(30,28,"wolf",42,9,22,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


def build_ruins():
    """Antik Harabeler — tek bağlantılı zemin, kesin erişilebilir geçişler."""
    m = GameMap(58, 52, "Antik Harabeler", ambient=(20,10,0))
    # Tümü zemin başlangıçta, sonra duvar ekle
    _rect(m, 0, 0, 58, 52, T.STONE)

    # 3x3 ızgara oda iç zeminleri (aralarında koridor bırakarak)
    # Sütun x: 2-14, 18-30, 34-52  |  Satır y: 2-12, 16-26, 30-46
    room_coords = [
        (2,2,13,11),   # r0c0
        (18,2,13,11),  # r0c1
        (34,2,19,11),  # r0c2
        (2,16,13,11),  # r1c0
        (18,16,13,11), # r1c1
        (34,16,19,11), # r1c2
        (2,30,13,17),  # r2c0
        (18,30,13,17), # r2c1
        (34,30,19,17), # r2c2 (boss)
    ]
    for rx,ry,rw,rh in room_coords:
        _rect(m, rx, ry, rw, rh, T.FLOOR)

    # Yatay koridorlar (geniş, garantili bağlantı)
    _rect(m, 15, 5, 3, 5, T.FLOOR)   # r0: c0-c1
    _rect(m, 31, 5, 3, 5, T.FLOOR)   # r0: c1-c2
    _rect(m, 15,19, 3, 5, T.FLOOR)   # r1: c0-c1
    _rect(m, 31,19, 3, 5, T.FLOOR)   # r1: c1-c2
    _rect(m, 15,33, 3, 9, T.FLOOR)   # r2: c0-c1
    _rect(m, 31,33, 3, 9, T.FLOOR)   # r2: c1-c2

    # Dikey koridorlar
    _rect(m,  6,13, 5, 3, T.FLOOR)   # c0: r0-r1
    _rect(m,  6,27, 5, 3, T.FLOOR)   # c0: r1-r2
    _rect(m, 22,13, 5, 3, T.FLOOR)   # c1: r0-r1
    _rect(m, 22,27, 5, 3, T.FLOOR)   # c1: r1-r2
    _rect(m, 40,13, 5, 3, T.FLOOR)   # c2: r0-r1
    _rect(m, 40,27, 5, 3, T.FLOOR)   # c2: r1-r2

    # RUINS_WALL (stone→wall komşu floora)
    for ty in range(52):
        for tx in range(58):
            if m.get(tx,ty)==T.STONE:
                if any(m.get(tx+dx,ty+dy)==T.FLOOR for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.RUINS_WALL)

    # Boss odası ayrımı (r2c2 = (34,30,19,17)) → iç alan bölünür
    # Boss alan: x=43..52, y=38..46
    for tx2 in range(34,53): m.set(tx2,38,T.RUINS_WALL)
    for ty2 in range(38,47): m.set(34,ty2,T.RUINS_WALL); m.set(52,ty2,T.RUINS_WALL)
    m.set(47,38,T.DOOR); m.set(48,38,T.DOOR)
    _rect(m, 35,39, 17, 7, T.FLOOR)

    # Geçişler — oda ZEMİNİNDEN (kesin erişilebilir)
    # Güney çıkış: r2c0 zemin içinden (x=4..13, y=46 sondan bir önceki satır)
    _add_trans(m, [(tx,46) for tx in range(3,13)]+[(tx,47) for tx in range(3,13)],
               "dark_forest", 26, 4, T.FLOOR, (0,1))
    # Doğu çıkış: r1c2 zemin içinden (x=52, y=18..25)
    _add_trans(m, [(52,ty) for ty in range(18,26)]+[(53,ty) for ty in range(18,26)],
               "desert", 3, 23, T.FLOOR, (1,0))

    # Sandıklar (oda içlerinde)
    m.set(5,  5,  T.CHEST); m.chests[(5,5)]   = ["hp_pot","mp_pot"]
    m.set(21, 5,  T.CHEST); m.chests[(21,5)]  = ["arcane_staff","gold"]
    m.set(40, 5,  T.CHEST); m.chests[(40,5)]  = ["mage_robe","gold"]
    m.set(5,  20, T.CHEST); m.chests[(5,20)]  = ["hp_pot","power_ring"]
    m.set(48, 43, T.CHEST); m.chests[(48,43)] = ["earth_c","hp_pot","hp_pot"]

    def ghost_d(f):
        if f.get("earth_crystal"): return ["Kristalin hakkini kullandin.","Bati Colu'ne git."]
        return ["Golem hala burada.","Dikkat et, cok guclu."]
    m.npcs.append(NPC(8, 21, "Antik Ruh", (180,200,220), ghost_d))
    m.enemies += [
        Enemy(6,  6, "skeleton",55,11,30,agro=5,loot=["gold"]),
        Enemy(22, 6, "skeleton",55,11,30,agro=5),
        Enemy(8, 20, "golem",   80,15,45,agro=4,loot=["gold","gold"]),
        Enemy(26,20, "skeleton",60,12,35,agro=5,loot=["hp_pot"]),
        Enemy(8, 34, "golem",   85,16,48,agro=4),
        Enemy(26,34, "skeleton",65,13,38,agro=5,loot=["mp_pot"]),
        Enemy(46,43, "golem",  130,20,80,agro=6,loot=["earth_c"],is_boss=True),
    ]
    _snap_all(m); return m


def build_desert():
    m = GameMap(60, 44, "Col Yolu", ambient=(30,15,0))
    _rect(m, 0, 0, 60, 44, T.SAND)
    # Sabit kaya grupları (yoldan uzak)
    for rx,ry,rs in [(6,6,3),(16,6,3),(52,6,3),(56,9,2),(6,36,3),(14,38,2),(52,36,3),(56,38,2)]:
        for ty in range(ry-rs,ry+rs+1):
            for tx in range(rx-rs,rx+rs+1):
                if (tx-rx)**2+(ty-ry)**2<=rs*rs and 2<=tx<58 and 2<=ty<42:
                    m.set(tx,ty,T.STONE)
    # Sabit kaktüsler
    for tx,ty in [(10,12),(20,8),(40,8),(50,14),(10,30),(20,36),(40,36),(50,28),(14,20),(46,20)]:
        if m.get(tx,ty)==T.SAND: m.set(tx,ty,T.CACTUS)
    # Vaha (merkez, biraz daha yukarı — y=14..22)
    for ty in range(14,22):
        for tx in range(26,36):
            if (tx-31)**2+(ty-18)**2<16: m.set(tx,ty,T.WATER)
    for ty in range(13,23):
        for tx in range(25,37):
            if m.get(tx,ty)==T.SAND:
                if any(m.get(tx+dx,ty+dy)==T.WATER for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.GRASS)
    # Oracle evi (vaha KUZEYİNDE, y=5..10, su alanından uzak)
    _room(m, 27, 5, 8, 6, T.WALL, T.FLOOR, "south")
    # Oracle evi ile yol arasında boş SAND (y=11..25 zaten sand)
    # Ana yol (vaha altında: y=28)
    _path(m, 2, 28, 58, 28, T.DIRT, 2)
    # Geçişler (yol üzerinde)
    _add_trans(m, [(0,ty) for ty in range(26,31)]+[(1,ty) for ty in range(26,31)],
               "ruins", 52, 21, T.SAND, (-1,0))
    _add_trans(m, [(58,ty) for ty in range(26,31)]+[(59,ty) for ty in range(26,31)],
               "ice_cave", 3, 28, T.SAND, (1,0))
    # Sandıklar (yol kenarında)
    m.set(5,  28, T.CHEST); m.chests[(5,28)]  = ["hp_pot","hp_pot","gold"]
    m.set(54, 28, T.CHEST); m.chests[(54,28)] = ["shadow_bow","gold"]
    m.set(30,  7, T.CHEST); m.chests[(30,7)]  = ["mage_focus","hp_pot"]
    def oracle_d(f):
        if f.get("water_crystal"): return ["Ikinci kristali buldun.","Artik Golge Kalesine gidebilirsin."]
        if f.get("earth_crystal"): return ["Hos geldin. Ikinci kristal Buz Magarasinda.","[ Gorev Guncellendi! ]"]
        return ["Henuz hazir degilsin.","Once Toprak Kristalini bul."]
    m.npcs.append(NPC(30, 8, "Oracle Nyx", (120,80,180), oracle_d, "oracle"))
    m.enemies += [
        Enemy(10,10,"scorpion",45,10,30,agro=5,loot=["gold"]),
        Enemy(48,10,"scorpion",45,10,30,agro=5),
        Enemy(10,34,"goblin",50,11,32,agro=5,loot=["hp_pot"]),
        Enemy(48,34,"goblin",50,11,32,agro=5,loot=["gold"]),
        Enemy(22,10,"scorpion",50,12,35,agro=6),
        Enemy(38,34,"goblin",55,12,35,agro=5,loot=["mp_pot"]),
    ]
    _snap_all(m); return m


def build_ice_cave():
    """Buz Mağarası — tüm odalar tek bağlantılı, geçişler oda zemininden."""
    m = GameMap(52, 48, "Buz Magara", ambient=(0,15,30))
    _rect(m, 0, 0, 52, 48, T.STONE)
    # 3x3 oda ızgarası (tek parça zemin)
    room_coords = [
        (2,2,12,11),(16,2,12,11),(30,2,20,11),
        (2,15,12,13),(16,15,12,13),(30,15,20,13),
        (2,30,12,16),(16,30,12,16),(30,30,20,16),
    ]
    for rx,ry,rw,rh in room_coords:
        _rect(m, rx, ry, rw, rh, T.SNOW)
    # Buz zeminleri (birkaç oda)
    _rect(m, 3, 3, 8, 6, T.ICE)
    _rect(m, 17, 3, 8, 6, T.ICE)
    _rect(m, 31, 3, 8, 6, T.ICE)
    # Yatay koridorlar
    _rect(m, 14,5, 2,5, T.SNOW); _rect(m, 28,5, 2,5, T.SNOW)
    _rect(m, 14,18,2,7, T.SNOW); _rect(m, 28,18,2,7, T.SNOW)
    _rect(m, 14,33,2,9, T.SNOW); _rect(m, 28,33,2,9, T.SNOW)
    # Dikey koridorlar
    _rect(m, 5,13, 5,2, T.SNOW); _rect(m, 5,28, 5,2, T.SNOW)
    _rect(m,19,13, 5,2, T.SNOW); _rect(m,19,28, 5,2, T.SNOW)
    _rect(m,36,13, 5,2, T.SNOW); _rect(m,36,28, 5,2, T.SNOW)
    # SNOW_TREE sadece dış çerçeve (ÜST+SAĞ, sol ve alt geçişler için boş)
    for tx in range(52): m.set(tx,0,T.SNOW_TREE); m.set(tx,1,T.SNOW_TREE)
    for ty in range(48): m.set(50,ty,T.SNOW_TREE); m.set(51,ty,T.SNOW_TREE)
    # Boss odası (r2c2 = (30,30,20,16) iç)
    for tx2 in range(30,50): m.set(tx2,36,T.STONE)
    for ty2 in range(36,46): m.set(30,ty2,T.STONE); m.set(49,ty2,T.STONE)
    m.set(39,36,T.DOOR); m.set(40,36,T.DOOR)
    _rect(m, 31,37, 18,8, T.ICE)
    # RUINS_WALL geçişi
    for ty in range(48):
        for tx in range(52):
            if m.get(tx,ty)==T.STONE:
                if any(m.get(tx+dx,ty+dy) in(T.SNOW,T.ICE) for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.STONE)  # kalsın taş (görsel)
    # Geçişler — oda zemininden (sol r1c0 + alt r2c0)
    # Sol geçiş: r1c0 = (2,15,12,13), sol duvar x=2. x=2 zemin, x=1,0 dışarı
    _add_trans(m, [(0,ty) for ty in range(17,25)]+[(1,ty) for ty in range(17,25)],
               "desert", 57, 27, T.SNOW, (-1,0))
    # Alt geçiş: r2c0 = (2,30,12,16), alt y=45. y=45 zemin
    _add_trans(m, [(tx,46) for tx in range(3,12)]+[(tx,47) for tx in range(3,12)],
               "shadow_castle", 22, 40, T.SNOW, (0,1))
    # Sandıklar (oda içleri)
    m.set(5,  5,  T.CHEST); m.chests[(5,5)]   = ["hp_pot","mp_pot"]
    m.set(19, 5,  T.CHEST); m.chests[(19,5)]  = ["scout_coat","gold"]
    m.set(5,  19, T.CHEST); m.chests[(5,19)]  = ["hp_pot","mp_pot"]
    m.set(38, 42, T.CHEST); m.chests[(38,42)] = ["water_c","hp_pot","mp_pot","hp_pot"]
    def spirit_d(f):
        if f.get("water_crystal"): return ["Kristali aldin.","Sol gecitten Golge Kalesine gidebilirsin!"]
        return ["Kristal boss odada.","Dikkat et!"]
    m.npcs.append(NPC(8, 20, "Buz Ruhu", (180,220,255), spirit_d))
    m.enemies += [
        Enemy(5,  5, "ice_wolf",55,12,35,agro=5,loot=["gold"]),
        Enemy(20, 5, "ice_wolf",55,12,35,agro=5),
        Enemy(33, 5, "golem",   75,14,42,agro=4,loot=["hp_pot"]),
        Enemy(8, 19, "ice_wolf",60,13,38,agro=5),
        Enemy(22,22, "golem",   80,15,45,agro=4,loot=["mp_pot"]),
        Enemy(8, 34, "golem",   85,16,50,agro=4,loot=["hp_pot"]),
        Enemy(40,41, "golem",  180,25,120,agro=7,loot=["water_c"],is_boss=True),
    ]
    _snap_all(m); return m


def build_shadow_castle():
    """Gölge Kalesi — açık zemin planı, tüm alanlar bağlantılı."""
    m = GameMap(56, 52, "Golge Kalesi", ambient=(40,0,60))
    _rect(m, 0, 0, 56, 52, T.SHADOW)
    # Tüm iç alanı zemin yap (duvarlar dekoratif)
    _rect(m, 2, 2, 52, 48, T.FLOOR)
    # Dekoratif gölge duvarlar (geçilebilir olmayan bölmeler, kapılı)
    # Üst sol oda bölmesi
    for tx in range(2,20): m.set(tx,18,T.WALL)
    for ty in range(18,34): m.set(2,ty,T.WALL); m.set(19,ty,T.WALL)
    m.set(10,18,T.DOOR); m.set(11,18,T.DOOR)   # kuzey kapı
    m.set(10,33,T.DOOR); m.set(11,33,T.DOOR)   # güney kapı
    # Üst sağ oda bölmesi
    for tx in range(36,54): m.set(tx,18,T.WALL)
    for ty in range(18,34): m.set(36,ty,T.WALL); m.set(53,ty,T.WALL)
    m.set(44,18,T.DOOR); m.set(45,18,T.DOOR)
    m.set(44,33,T.DOOR); m.set(45,33,T.DOOR)
    # Merkez boss bölmesi
    for tx in range(20,36): m.set(tx,22,T.WALL); m.set(tx,30,T.WALL)
    for ty in range(22,31): m.set(20,ty,T.WALL); m.set(35,ty,T.WALL)
    m.set(27,22,T.DOOR); m.set(28,22,T.DOOR)
    m.set(27,30,T.DOOR); m.set(28,30,T.DOOR)
    # Geçiş (sol duvar, açık alan içinden)
    _add_trans(m, [(2,ty) for ty in range(23,30)]+[(3,ty) for ty in range(23,30)],
               "ice_cave", 8, 44, T.FLOOR, (-1,0))
    # Sandıklar
    m.set(5,  5,  T.CHEST); m.chests[(5,5)]   = ["hp_pot","hp_pot","mp_pot"]
    m.set(48, 5,  T.CHEST); m.chests[(48,5)]  = ["warrior_crest","hp_pot"]
    m.set(5,  44, T.CHEST); m.chests[(5,44)]  = ["hp_pot","hp_pot","steel_sword"]
    m.set(48, 44, T.CHEST); m.chests[(48,44)] = ["mage_focus","elder_staff"]
    def king_d(f):
        if f.get("malachar_defeated"): return ["Kahraman! Krallik sana borclu!"]
        return ["Malachar cok guclu. Her iki kristal gerekmekte."]
    m.npcs.append(NPC(10, 8, "Kral Alderon", (200,160,80), king_d, "guard"))
    m.enemies += [
        Enemy(8,  8, "shadow_knight",100,20,65,agro=6,loot=["hp_pot","gold"]),
        Enemy(46, 8, "shadow_knight",100,20,65,agro=6,loot=["hp_pot"]),
        Enemy(8, 44, "shadow_knight",110,22,70,agro=6,loot=["mp_pot","gold"]),
        Enemy(46,44, "shadow_knight",110,22,70,agro=6,loot=["gold"]),
        Enemy(10,24, "shadow_knight",120,24,75,agro=7,loot=["hp_pot","mp_pot"]),
        Enemy(44,24, "shadow_knight",120,24,75,agro=7),
        Enemy(27,26, "malachar",500,35,999,agro=10,loot=["gold","gold"],is_boss=True),
    ]
    _snap_all(m); return m


def build_village_dungeon():
    """Zindan — 4 oda tek bağlantılı zemin."""
    m = GameMap(40, 34, "Koy Altı Zindanı", ambient=(10,5,20))
    _rect(m, 0, 0, 40, 34, T.STONE)
    for tx in range(40): m.set(tx,0,T.RUINS_WALL); m.set(tx,33,T.RUINS_WALL)
    for ty in range(34): m.set(0,ty,T.RUINS_WALL); m.set(39,ty,T.RUINS_WALL)
    # 4 oda (tüm iç alan tek parça)
    _rect(m,  2,  2, 16, 12, T.FLOOR)
    _rect(m, 22,  2, 16, 12, T.FLOOR)
    _rect(m,  2, 18, 16, 14, T.FLOOR)
    _rect(m, 22, 18, 16, 14, T.FLOOR)
    # Koridorlar
    _rect(m, 17,  4,  6,  7, T.FLOOR)
    _rect(m, 17, 19,  6,  9, T.FLOOR)
    _rect(m,  5, 13,  9,  5, T.FLOOR)
    _rect(m, 26, 13,  9,  5, T.FLOOR)
    # Duvar düzelt
    for ty in range(34):
        for tx in range(40):
            if m.get(tx,ty)==T.STONE:
                if any(m.get(tx+dx,ty+dy)==T.FLOOR for dx,dy in[(-1,0),(1,0),(0,-1),(0,1)]):
                    m.set(tx,ty,T.RUINS_WALL)
    # Çıkış (oda1 içinden)
    _add_trans(m, [(tx,2) for tx in range(6,12)]+([(tx,3) for tx in range(6,12)]),
               "ashveil", 28, 45, T.FLOOR, (0,-1))
    m.set(6,  5,  T.CHEST); m.chests[(6,5)]   = ["hp_pot","mp_pot","gold"]
    m.set(30, 5,  T.CHEST); m.chests[(30,5)]  = ["steel_sword","leather_armor","gold"]
    m.set(6,  26, T.CHEST); m.chests[(6,26)]  = ["arcane_staff","mage_robe"]
    m.set(30, 26, T.CHEST); m.chests[(30,26)] = ["hp_pot","hp_pot","mp_pot","swift_boots"]
    m.enemies += [
        Enemy(12, 7, "skeleton",70,14,45,agro=5,loot=["gold","gold"]),
        Enemy(28, 6, "golem",  100,18,60,agro=4,loot=["hp_pot","gold"]),
        Enemy(8,  26,"skeleton",80,16,50,agro=5,loot=["mp_pot"]),
        Enemy(30, 26,"golem",  110,20,65,agro=4,loot=["gold","gold"]),
        Enemy(20, 22,"skeleton",90,17,55,agro=6,loot=["hp_pot","gold"]),
    ]
    _snap_all(m); return m


def build_south_meadow():
    m = GameMap(56, 42, "Guney Cayiri")
    _rect(m, 0, 0, 56, 42, T.GRASS)
    _rect(m, 5, 10, 20, 14, T.FARMLAND)
    _rect(m, 28,10, 18, 14, T.WHEAT)
    # Çit (girişli)
    for tx in range(4,48): m.set(tx,9,T.FENCE); m.set(tx,25,T.FENCE)
    for ty in range(9,26): m.set(4,ty,T.FENCE); m.set(47,ty,T.FENCE)
    m.set(20,9,T.GRASS); m.set(21,9,T.GRASS)
    m.set(20,25,T.GRASS); m.set(21,25,T.GRASS)
    _room(m, 5, 28,14,10,T.WALL,T.FLOOR,"north")
    _room(m,22, 28,10, 8,T.WALL,T.FLOOR,"north")
    _path(m,20,  0,20,10,T.DIRT,2)
    _path(m, 5, 22,52,22,T.DIRT,2)
    for ty in range(30,40):
        for tx in range(42,54):
            if (tx-48)**2+(ty-35)**2<22: m.set(tx,ty,T.WATER)
    for tx in range(56): m.set(tx,40,T.TREE); m.set(tx,41,T.TREE)
    for ty in range(42): m.set(55,ty,T.TREE)
    _add_trans(m, [(tx,0) for tx in range(16,26)]+[(tx,1) for tx in range(16,26)],
               "ashveil", 23, 47, T.GRASS, (0,-1))
    m.set(8,  30, T.CHEST); m.chests[(8,30)]  = ["farm_tool","hp_pot","gold"]
    m.set(46, 22, T.CHEST); m.chests[(46,22)] = ["hp_pot","mana_gem"]
    def farmer_d(f): return ["Hos geldin! Ben Ciftci Torben.","Yabanl hayvanlar artti.","Aletlerim sandikta."]
    m.npcs.append(NPC(10,30,"Ciftci Torben",(160,120,80),farmer_d,"farmer"))
    def kid_d(f): return ["Seninle oynar miyim kahraman?"]
    m.npcs.append(NPC(35,12,"Ciftlik Cocugu",(180,200,160),kid_d))
    def traveler_d(f): return ["Guzel cayirlar.","Batıda nehir var."]
    m.npcs.append(NPC(50,22,"Gezgin",(140,150,180),traveler_d))
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
    m = GameMap(56, 42, "Bati Nehri", ambient=(0,10,20))
    _rect(m, 0, 0, 56, 42, T.GRASS)
    # Nehir
    for ty in range(42):
        for tx in range(25,31): m.set(tx,ty,T.RIVER)
    # Köprüler (yollarla hizalı: y=9..12 ve y=27..30)
    for tx in range(25,31):
        for ty in range(9,13):  m.set(tx,ty,T.BRIDGE)
        for ty in range(27,31): m.set(tx,ty,T.BRIDGE)
    # Yollar
    _path(m, 0,10,25,10,T.DIRT,2); _path(m,31,10,56,10,T.DIRT,2)
    _path(m, 0,28,25,28,T.DIRT,2); _path(m,31,28,56,28,T.DIRT,2)
    # Balıkçı kulübesi
    _room(m, 3,14,10, 8,T.WALL,T.FLOOR,"east")
    # Sabit ağaç grupları
    for ty in range(0,8):
        for tx in range(0,10):
            if tx%3<2 and ty%3<2: m.set(tx,ty,T.TREE)
    for ty in range(33,42):
        for tx in range(35,56):
            if (tx-35)%3<2 and (ty-33)%3<2: m.set(tx,ty,T.TREE)
    # Doğu geçişi
    _add_trans(m, [(54,ty) for ty in range(18,28)]+[(55,ty) for ty in range(18,28)],
               "ashveil", 3, 24, T.GRASS, (1,0))
    m.set(5,  16, T.CHEST); m.chests[(5,16)]  = ["river_gem","mp_pot","gold"]
    m.set(46,  5, T.CHEST); m.chests[(46,5)]  = ["hp_pot","hp_pot","mana_gem"]
    m.set(46, 33, T.CHEST); m.chests[(46,33)] = ["fine_bow","gold"]
    def fisher_d(f): return ["Hos geldin! Ben Balikci Riva.","Bu nehir eskiden temizdi."]
    m.npcs.append(NPC(6,16,"Balikci Riva",(100,140,180),fisher_d))
    def hermit_d(f): return ["Uzlette yasiyorum."]
    m.npcs.append(NPC(44,4,"Munzevi",(180,160,200),hermit_d))
    m.enemies += [
        Enemy(18, 4,"slime",   30, 6,18,agro=4,loot=["gold"]),
        Enemy(40, 4,"goblin",  38, 8,22,agro=5,loot=["hp_pot"]),
        Enemy(14,34,"wolf",    42, 9,25,agro=5),
        Enemy(40,34,"goblin",  45,10,28,agro=5,loot=["gold"]),
        Enemy(36,18,"skeleton",50,11,30,agro=5,loot=["mp_pot"]),
        Enemy(40,22,"skeleton",50,11,30,agro=5,loot=["gold"]),
    ]
    _snap_all(m); return m


# ─── UI ─────────────────────────────────────────────────────────
class UI:
    def __init__(self):
        self.fsm=pygame.font.SysFont("monospace",9, bold=True)
        self.fss=pygame.font.SysFont("monospace",11,bold=True)
        self.fmd=pygame.font.SysFont("monospace",14,bold=True)
        self.flg=pygame.font.SysFont("monospace",20,bold=True)
        self.fxl=pygame.font.SysFont("monospace",28,bold=True)
        self.fti=pygame.font.SysFont("monospace",34,bold=True)

    def txt(self,surf,text,x,y,col=UI_TX,fnt=None,shadow=True):
        f=fnt or self.fss
        if shadow: surf.blit(f.render(text,True,BK),(x+1,y+1))
        surf.blit(f.render(text,True,col),(x,y))

    def grad_bar(self,surf,x,y,w,h,val,mx,c1,c2,bg=(20,10,35)):
        pygame.draw.rect(surf,bg,(x,y,w,h))
        fill=int(w*max(0,val)/max(1,mx))
        for i in range(fill):
            tt=i/max(1,fill);rr=int(c1[0]+(c2[0]-c1[0])*tt);gg=int(c1[1]+(c2[1]-c1[1])*tt);bb=int(c1[2]+(c2[2]-c1[2])*tt)
            pygame.draw.line(surf,(rr,gg,bb),(x+i,y),(x+i,y+h-1))
        if fill>4:
            sh=pygame.Surface((fill,h),pygame.SRCALPHA);sh.fill((255,255,255,20));surf.blit(sh,(x,y))
        pygame.draw.rect(surf,UI_BD,(x,y,w,h),1)

    def panel(self,surf,x,y,w,h,alpha=220,glow=False):
        s=pygame.Surface((w,h),pygame.SRCALPHA)
        for i in range(h):
            tt=i/h;rr=int(UI_BG[0]+4*tt);gg=int(UI_BG[1]+2*tt);bb=int(UI_BG[2]+12*tt)
            pygame.draw.line(s,(rr,gg,bb,alpha),(0,i),(w,i))
        pygame.draw.rect(s,UI_BD,(0,0,w,h),2)
        if glow:
            gv=int(abs(math.sin(pygame.time.get_ticks()*0.002))*50)+20
            pygame.draw.rect(s,(*UI_AC,gv),(0,0,w,h),3)
        surf.blit(s,(x,y))

    def draw_hud(self,surf,player,map_name,chapter,quest_name,tick):
        st=player.stats;cc=CLASS_COL.get(st.char_class,(100,100,200))
        ci=CLASS_INFO[st.char_class]
        # Sol panel 270x125
        self.panel(surf,6,6,270,125)
        pygame.draw.rect(surf,cc,(10,10,3,112))
        # Başlık
        self.txt(surf,f"{ci['name']}  Sv.{st.level}",18,10,cc,self.fmd)
        # Barlar
        self.txt(surf,"HP",18,30,HP_G,self.fsm)
        self.grad_bar(surf,36,30,226,10,st.hp,st.max_hp,(80,15,15),HP_G)
        self.txt(surf,f"{st.hp}/{st.max_hp}",38,31,(220,255,220),self.fsm)
        self.txt(surf,"MP",18,44,MP_B,self.fsm)
        self.grad_bar(surf,36,44,226,10,st.mp,st.max_mp,(10,15,60),UI_CY)
        self.txt(surf,f"{st.mp}/{st.max_mp}",38,45,(180,220,255),self.fsm)
        self.txt(surf,"XP",18,58,XP_T,self.fsm)
        self.grad_bar(surf,36,58,226,8,st.xp,st.xp_next,(15,45,35),XP_T)
        # Stats (tek satır)
        self.txt(surf,f"ATK:{st.attack}  DEF:{st.defense}  AGI:{st.agi+st._equip_bonus('agi')}",18,72,LGR,self.fsm)
        # Altın + puan
        gp=int(abs(math.sin(tick*0.003))*15)
        self.txt(surf,f"Gold:{st.gold}",18,86,(230+gp,180,40),self.fsm)
        if st.skill_points>0:
            sc=(255,220,50) if (tick//500)%2==0 else (200,160,30)
            self.txt(surf,f"[U]+{st.skill_points} Puan!",140,86,sc,self.fsm)
        # Bufflar
        by=102
        if "war_cry" in st.buffs:   self.txt(surf,"SAVAS CIGLIK",18,by,(255,120,50),self.fsm)
        elif "holy_shield" in st.buffs: self.txt(surf,"KUTSAL KALKAN",18,by,(255,220,60),self.fsm)
        # Ekipman özeti (küçük)
        eq_strs=[]
        for slot,ik in st.equipment.items():
            if ik and ik in EQUIP_ITEMS: eq_strs.append(EQUIP_ITEMS[ik][0][:8])
        if eq_strs: self.txt(surf,"  ".join(eq_strs[:2]),18,by if "war_cry" not in st.buffs and "holy_shield" not in st.buffs else by+12,(100,120,160),self.fsm)

        # Üst merkez — harita + bölüm (ayrı satırlar)
        mn=self.fmd.render(map_name,True,UI_AC)
        surf.blit(mn,(SW//2-mn.get_width()//2,6))
        qn=f"Bolum {chapter}: {quest_name[:30]}"
        qt=self.fsm.render(qn,True,UI_GD)
        surf.blit(qt,(SW//2-qt.get_width()//2,26))
        # Saldırı türü
        atk_name=CLASS_INFO[st.char_class]["atk_name"]
        at=self.fsm.render(f"[Spc]{atk_name}",True,(120,160,120))
        surf.blit(at,(SW//2-at.get_width()//2,42))

        # Sağ üst kontroller (çok küçük, şeffaf)
        tips=["[WASD]Hareket","[E]Konus/Ac","[Spc]Saldiri","[1-4]Yetenek","[I]Envanter","[Q]Gorev"]
        for i,tip in enumerate(tips):
            t2=self.fsm.render(tip,True,(55,65,75))
            surf.blit(t2,(SW-t2.get_width()-6,8+i*13))

    def draw_ability_bar(self,surf,stats,tick):
        ab_list=ABILITIES.get(stats.char_class,[])
        slot_w=54;bar_w=slot_w*4+8;bar_h=62
        bx=SW//2-bar_w//2;by=SH-bar_h-6
        self.panel(surf,bx-2,by-2,bar_w+4,bar_h+4)
        for i,ab in enumerate(ab_list):
            sx=bx+i*slot_w;sy=by
            locked=stats.level<ab["level"];on_cd=stats.ab_cds[i]>0;no_mp=stats.mp<ab["mp"]
            col=ab["col"]
            ss=pygame.Surface((slot_w-2,bar_h),pygame.SRCALPHA)
            if locked: ss.fill((25,15,35,200))
            elif on_cd: ss.fill((18,12,28,200))
            else: ss.fill((*col,55))
            pygame.draw.rect(ss,col if not locked else GR,(0,0,slot_w-2,bar_h),2)
            surf.blit(ss,(sx,sy))
            self.txt(surf,str(i+1),sx+3,sy+2,UI_GD if not locked else GR,self.fsm,shadow=False)
            pygame.draw.circle(surf,col if not locked else GR,(sx+slot_w//2-1,sy+21),11)
            if not locked: pygame.draw.circle(surf,WH,(sx+slot_w//2-1,sy+21),11,1)
            if on_cd:
                max_cd=ab["cd"];frac=stats.ab_cds[i]/max_cd
                cd_s=pygame.Surface((24,24),pygame.SRCALPHA);pygame.draw.circle(cd_s,(0,0,0,160),(12,12),11)
                ang2=int(360*frac)
                if ang2>0: pygame.draw.arc(cd_s,(255,255,255,180),(1,1,22,22),math.radians(90),math.radians(90+ang2),4)
                surf.blit(cd_s,(sx+slot_w//2-13,sy+9))
                cd_txt=self.fsm.render(str(stats.ab_cds[i]//FPS+1),True,WH)
                surf.blit(cd_txt,(sx+slot_w//2-1-cd_txt.get_width()//2,sy+16))
            c2=GR if locked else(UI_TX if not on_cd else GR)
            self.txt(surf,ab["name"][:7],sx+1,sy+36,c2,self.fsm,shadow=False)
            mc=UI_RD if(no_mp and not locked) else GR
            self.txt(surf,f"MP:{ab['mp']}",sx+1,sy+48,mc,self.fsm,shadow=False)
            if locked:
                lk=self.fsm.render(f"Sv{ab['level']}",True,(160,80,80))
                surf.blit(lk,(sx+slot_w//2-1-lk.get_width()//2,sy+17))

    def draw_inventory(self,surf,player,sel,eq_tab,tick):
        """Tam Envanter + Ekipman sistemi."""
        pw,ph=640,440;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        # Sekmeler
        for i,(tname,tcol) in enumerate([("Esyalar",UI_TX),("Ekipman",UI_GD)]):
            active=(i==eq_tab)
            ts=pygame.Surface((100,24),pygame.SRCALPHA)
            ts.fill((*UI_AC,80) if active else (*UI_BD,30))
            pygame.draw.rect(ts,UI_AC if active else UI_BD,(0,0,100,24),2)
            surf.blit(ts,(px+16+i*108,py+8))
            self.txt(surf,tname,px+22+i*108,py+11,UI_AC if active else GR,self.fss,shadow=False)
        self.txt(surf,f"Gold:{player.stats.gold}",px+pw-110,py+10,UI_GD,self.fmd)

        if eq_tab==0:
            # ─── Eşya sekmesi ─────────────────────────────────
            unique:Dict={};all_inv=player.inventory[:]
            for k in all_inv: unique[k]=unique.get(k,0)+1
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
                # İkon arka planı
                ic=itm[1];pygame.draw.rect(surf,ic,(ix+8,iy+8,40,40));pygame.draw.rect(surf,WH,(ix+8,iy+8,40,40),1)
                if itm[2]=="equip":
                    eic=PA.equip_icon(itm[3],ic);surf.blit(eic,(ix+10,iy+10))
                self.txt(surf,itm[0][:10],ix+4,iy+52,WH,self.fsm)
                if cnt>1: self.txt(surf,f"x{cnt}",ix+96,iy+8,UI_GD,self.fsm)
                if itm[2]=="equip":
                    # Ekipli mi?
                    if k in player.stats.equipment.values():
                        ep=pygame.Surface((116,86),pygame.SRCALPHA);ep.fill((40,200,80,40))
                        pygame.draw.rect(ep,(40,200,80,120),(0,0,116,86),3);surf.blit(ep,(ix,iy))
                        self.txt(surf,"EKIPLi",ix+56,iy+8,UI_GN,self.fsm)
            # Seçili eşya bilgisi
            if 0<=sel<len(all_keys):
                si=ALL_ITEMS.get(all_keys[sel])
                if si:
                    self.txt(surf,si[0],px+14,py+ph-62,UI_AC,self.fmd)
                    self.txt(surf,si[4],px+14,py+ph-44,LGR,self.fss)
                    if si[2]=="equip":
                        ek=all_keys[sel];_,_,_,slot,cls_set=EQUIP_ITEMS[ek]
                        current=player.stats.equipment.get(slot)
                        if current==ek: self.txt(surf,"[ E ] Cıkar",px+14,py+ph-26,UI_RD,self.fss)
                        else: self.txt(surf,f"[ E ] Giy ({slot})",px+14,py+ph-26,UI_GN,self.fss)
                    elif si[2] in("heal","mana"): self.txt(surf,"[ E ] Kullan",px+14,py+ph-26,UI_GN,self.fss)
        else:
            # ─── Ekipman sekmesi ───────────────────────────────
            st=player.stats
            slot_data=[("weapon","Silah",UI_RD),("armor","Zırh",ST_L),("ring","Yuzuk",UI_GD)]
            for si2,(slot,sname,scol) in enumerate(slot_data):
                iy=py+48+si2*110
                # Slot kutusu
                ss=pygame.Surface((pw-28,100),pygame.SRCALPHA)
                ss.fill((*UI_BD,25));pygame.draw.rect(ss,scol,(0,0,pw-28,100),2)
                surf.blit(ss,(px+14,iy))
                ik=st.equipment.get(slot)
                # Slot ikonu
                ic_s=PA.equip_icon(slot,scol);surf.blit(ic_s,(px+20,iy+30))
                self.txt(surf,sname,px+64,iy+8,scol,self.fmd)
                if ik and ik in EQUIP_ITEMS:
                    edata=EQUIP_ITEMS[ik]
                    self.txt(surf,edata[0],px+64,iy+34,WH,self.fss)
                    bonus_str=" | ".join(f"{k.upper()}+{v}" for k,v in edata[2].items())
                    self.txt(surf,bonus_str,px+64,iy+56,UI_GN,self.fsm)
                    self.txt(surf,"[ E ] Cıkar",px+64,iy+76,UI_RD,self.fsm)
                else:
                    self.txt(surf,"— Bos —",px+64,iy+36,GR,self.fss)
                    self.txt(surf,"Esya sekmesinden ekipman giy",px+64,iy+56,GR,self.fsm)
            # Toplam bonus
            bx2=px+14;by2=py+ph-56
            self.txt(surf,"Ekipman Bonusu:",bx2,by2,UI_GD,self.fss)
            stats_show=[("str",HP_R),("int",UI_BL),("agi",UI_GN),("vit",UI_GD),("wis",UI_PR)]
            for si3,(sk,sc) in enumerate(stats_show):
                b=st._equip_bonus(sk)
                if b>0: self.txt(surf,f"+{b}{sk.upper()}",bx2+si3*80,by2+20,sc,self.fsm)
        self.txt(surf,"[Tab]Sekme  [I/ESC]Kapat  [Yon]Sec  [E]Kullan/Giy",px+14,py+ph-12,GR,self.fsm)

    def draw_dialog(self,surf,npc_name,lines,page,total):
        bh=112;bx=8;by=SH-bh-8
        self.panel(surf,bx,by,SW-16,bh,glow=True)
        pygame.draw.rect(surf,UI_BD,(bx,by-2,len(npc_name)*8+16,18))
        self.txt(surf,npc_name,bx+8,by,UI_AC,self.fmd,shadow=False)
        for i,line in enumerate(lines[:4]):
            col=UI_GD if line.startswith("[") else UI_TX
            self.txt(surf,line,bx+14,by+22+i*20,col,self.fss)
        if(pygame.time.get_ticks()//600)%2==0: self.txt(surf,"[ E ] Devam",SW-130,by+bh-20,UI_AC,self.fsm)
        if total>1: self.txt(surf,f"{page}/{total}",SW-50,by+4,GR,self.fsm)

    def draw_quest_log(self,surf,flags,chapter):
        pw,ph=500,365;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        self.txt(surf,"GOREV GUNLUGU",px+16,py+10,UI_GD,self.flg)
        y_off=50
        for ch,qdata in QUESTS.items():
            qname,qdesc=qdata
            if ch<chapter:
                pygame.draw.rect(surf,(*UI_GN,28),(px+12,py+y_off-2,pw-24,34))
                self.txt(surf,f"[V] Bolum {ch}: {qname}",px+18,py+y_off,UI_GN,self.fss)
                self.txt(surf,"    Tamamlandi",px+18,py+y_off+16,GR,self.fsm)
            elif ch==chapter:
                pv=int(abs(math.sin(pygame.time.get_ticks()*0.003))*25)
                pygame.draw.rect(surf,(*UI_GD,38+pv),(px+12,py+y_off-2,pw-24,34))
                pygame.draw.rect(surf,UI_GD,(px+12,py+y_off-2,pw-24,34),2)
                self.txt(surf,f"[>] Bolum {ch}: {qname}",px+18,py+y_off,UI_GD,self.fmd)
                self.txt(surf,f"    {qdesc}",px+18,py+y_off+16,UI_TX,self.fsm)
            else:
                self.txt(surf,f"[?] Bolum {ch}: ???",px+18,py+y_off,(55,55,65),self.fss)
            y_off+=38
        self.txt(surf,"[Q/ESC] Kapat",px+14,py+ph-22,GR,self.fss)

    def draw_stat_alloc(self,surf,stats,free,sel,is_lu=False,tick=0):
        pw,ph=510,430;px=SW//2-pw//2;py=SH//2-ph//2
        self.panel(surf,px,py,pw,ph,glow=True)
        title="SEVIYE ATLADI!" if is_lu else "NITELIK DAGITIMI"
        col=UI_GD if is_lu else UI_AC
        self.txt(surf,title,px+pw//2-len(title)*5,py+12,col,self.flg)
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
            self.txt(surf,sname,px+20,sy2+6,sc2,self.fmd)
            self.txt(surf,STAT_DESCS[sk],px+20,sy2+26,GR,self.fsm)
            self.txt(surf,"[<]",px+pw-140,sy2+12,(200,100,100) if val>2 else GR,self.fmd)
            self.txt(surf,str(val),px+pw-100,sy2+12,WH,self.flg)
            if eq_b>0: self.txt(surf,f"+{eq_b}",px+pw-75,sy2+18,UI_GN,self.fsm)
            self.txt(surf,"[>]",px+pw-56,sy2+12,(100,200,100) if free>0 else GR,self.fmd)
            self.grad_bar(surf,px+165,sy2+18,180,11,val+eq_b,25,(20,10,40),sc2)
        self.txt(surf,"[Yon]Sec  [</> ]Degistir  [ENTER]Onayla",px+16,py+ph-24,GR,self.fsm)

    def draw_class_select(self,surf,sel,tick):
        surf.fill(DKG)
        for i in range(120):
            random.seed(i*137+42);sx2=random.randint(0,SW);sy2=random.randint(0,SH//2);br=random.randint(60,180)
            pygame.draw.circle(surf,(br,br,br),(sx2,sy2),1)
        random.seed()
        self.txt(surf,"SINIF SEC",SW//2-100,26,UI_AC,self.fxl)
        self.txt(surf,"Karakterin icin bir yol sec",SW//2-130,62,LGR,self.fmd)
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
            nm=self.fmd.render(ci["name"],True,cc if sel_this else LGR);surf.blit(nm,(cx2+cw//2-nm.get_width()//2,cy2+74))
            # Saldırı türü
            self.txt(surf,f"Sld:{ci['atk_name'][:12]}",cx2+6,cy2+96,UI_GD if sel_this else GR,self.fsm,shadow=False)
            # Stat çubukları
            bonus=ci["bonus"]
            stat_labels=[("GUC","str",HP_R),("ZEKA","int",UI_BL),("CEV","agi",UI_GN),("DAY","vit",UI_GD),("BIL","wis",UI_PR)]
            for si2,(slbl,sk,scol) in enumerate(stat_labels):
                sv=2+bonus.get(sk,0)
                self.txt(surf,slbl,cx2+6,cy2+112+si2*22,LGR,self.fsm,shadow=False)
                self.grad_bar(surf,cx2+40,cy2+112+si2*22,cw-48,9,sv,12,(20,10,40),scol)
            for li,ln in enumerate(ci["lore"].split("\n")):
                self.txt(surf,ln,cx2+6,cy2+236+li*16,(*cc,200) if sel_this else GR,self.fsm,shadow=False)
        pv=int(abs(math.sin(tick*0.003))*80)+120
        self.txt(surf,"[</> ] Sec   [E/ENTER] Onayla",SW//2-140,SH-38,(int(pv),100,255),self.fmd)

    def draw_story(self,surf,lines_shown,tick):
        surf.fill(DKG)
        for i in range(80):
            random.seed(i*251);sx2=random.randint(0,SW);sy2=random.randint(0,SH);br=random.randint(50,160)
            pygame.draw.circle(surf,(br,br,br),(sx2,sy2),1)
        random.seed()
        self.txt(surf,TITLE,SW//2-len(TITLE)*9,36,UI_AC,self.fxl)
        for i,(line,col) in enumerate(STORY_LINES[:lines_shown]):
            y=130+i*30
            if line==" " or y>SH-50: continue
            ts=self.fmd.render(line,True,col);surf.blit(ts,(SW//2-ts.get_width()//2,y))
        if lines_shown>=len(STORY_LINES):
            pv=int(abs(math.sin(tick*0.003))*80)+120
            self.txt(surf,"[ ENTER ] Devam",SW//2-90,SH-60,(int(pv),120,255),self.flg)

    def draw_title(self,surf,tick):
        surf.fill(DKG)
        for i in range(150):
            random.seed(i*137);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.001+i*0.3))*100)+80
            br=(min(255,pv//2),min(255,pv//3),min(255,pv));pygame.draw.circle(surf,br,(sx2,sy2),1)
        random.seed()
        tt=self.fti.render(TITLE,True,UI_AC)
        surf.blit(self.fti.render(TITLE,True,(50,30,80)),(SW//2-tt.get_width()//2+3,143));surf.blit(tt,(SW//2-tt.get_width()//2,140))
        self.txt(surf,"v4.0 — Sinifa Ozgun Saldiri | Ekipman Sistemi",SW//2-200,190,UI_GD,self.fmd)
        for i2,cls in enumerate(CLASS_INFO.keys()):
            sp=PA.player_surf("down",tick//50,cls);surf.blit(pygame.transform.scale(sp,(56,56)),(SW//2-112+i2*56,240))
        pv2=int(abs(math.sin(tick*0.003))*80)+120
        btn=pygame.Surface((300,42),pygame.SRCALPHA);btn.fill((*UI_BD,90));pygame.draw.rect(btn,UI_AC,(0,0,300,42),2);surf.blit(btn,(SW//2-150,320))
        self.txt(surf,"[ ENTER ]  Maceraya Basla",SW//2-120,330,(int(pv2*0.8),100,255),self.fmd)
        self.txt(surf,"WASD Hareket  E Konus  Spc Saldiri  1-4 Yetenek  I Envanter",SW//2-250,386,GR,self.fsm)

    def draw_levelup_popup(self,surf,level,tick):
        pw,ph=380,76;px=SW//2-pw//2;py=100
        s=pygame.Surface((pw,ph),pygame.SRCALPHA);s.fill((25,15,45,215))
        gv=int(abs(math.sin(tick*0.004))*40)+40;pygame.draw.rect(s,(*UI_GD,gv+100),(0,0,pw,ph),3)
        tt=self.flg.render(f"SEVIYE {level} !",True,UI_GD);s.blit(tt,(pw//2-tt.get_width()//2,8))
        t2=self.fss.render("[U] Nitelik puan dagit!",True,UI_TX);s.blit(t2,(pw//2-t2.get_width()//2,38))
        surf.blit(s,(px,py))

    def draw_gameover(self,surf):
        ov=pygame.Surface((SW,SH),pygame.SRCALPHA);ov.fill((0,0,0,185));surf.blit(ov,(0,0))
        self.txt(surf,"OLDUN",SW//2-60,SH//2-70,HP_R,self.fxl)
        self.txt(surf,"Karanlik seni yuttu...",SW//2-120,SH//2-10,LGR,self.fmd)
        self.txt(surf,"[ R ] Yeniden Basla",SW//2-100,SH//2+40,UI_AC,self.fmd)

    def draw_victory(self,surf,tick):
        surf.fill(DKG)
        for i in range(200):
            random.seed(i*313);sx2=random.randint(0,SW);sy2=random.randint(0,SH)
            pv=int(abs(math.sin(tick*0.002+i*0.5))*120)+80;pygame.draw.circle(surf,(pv,int(pv*0.8),50),(sx2,sy2),1)
        random.seed()
        gv=int(abs(math.sin(tick*0.002))*60)+80
        self.txt(surf,"ZAFER!",SW//2-80,120,(255,gv+80,gv//2),self.fti)
        self.txt(surf,"Malachar yenildi!",SW//2-130,200,UI_GD,self.fxl)
        self.txt(surf,"Dunya bir kez daha kurtarildi.",SW//2-180,260,UI_TX,self.flg)
        self.txt(surf,"[ ESC ] Ana Menu",SW//2-100,380,(int(abs(math.sin(tick*0.003))*100)+120,100,255),self.fmd)

    def draw_transition(self,surf,alpha,name):
        ov=pygame.Surface((SW,SH),pygame.SRCALPHA);ov.fill((0,0,0,min(255,alpha)));surf.blit(ov,(0,0))
        if alpha>120:
            t=self.flg.render(name,True,UI_AC);t.set_alpha(min(255,alpha*2-240));surf.blit(t,(SW//2-t.get_width()//2,SH//2-16))

    def draw_chapter(self,surf,chapter,alpha):
        if chapter not in QUESTS: return
        ov=pygame.Surface((SW,SH),pygame.SRCALPHA);ov.fill((0,0,0,min(150,alpha)));surf.blit(ov,(0,0))
        t=self.fti.render(f"Bolum {chapter}",True,UI_GD);t.set_alpha(min(255,alpha));surf.blit(t,(SW//2-t.get_width()//2,SH//2-55))
        t2=self.flg.render(QUESTS[chapter][0],True,UI_AC);t2.set_alpha(min(255,alpha));surf.blit(t2,(SW//2-t2.get_width()//2,SH//2+10))


# ─── Game ────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        self.screen=pygame.display.set_mode((SW,SH));pygame.display.set_caption(TITLE)
        self.clock=pygame.time.Clock();self.ui=UI();self.ps=PS();self._reset()

    def _reset(self):
        self.maps={
            "ashveil":build_ashveil(),"dark_forest":build_dark_forest(),
            "ruins":build_ruins(),"desert":build_desert(),"ice_cave":build_ice_cave(),
            "shadow_castle":build_shadow_castle(),"village_dungeon":build_village_dungeon(),
            "south_meadow":build_south_meadow(),"west_river":build_west_river(),
        }
        self.cur_key="ashveil";self.cur_map=self.maps["ashveil"]
        self.state="title";self.tick=0
        self.class_sel=0;self.stat_sel=0;self.free_pts=10
        self.temp_stats:Optional[PlayerStats]=None;self.is_lu=False
        self.story_shown=0;self.story_timer=0
        self.flags={"ch":1,"speak_aldric":False,"earth_crystal":False,
                    "speak_oracle":False,"water_crystal":False,"malachar_defeated":False}
        self.player:Optional[Player]=None
        self.cam_x=0;self.cam_y=0;self.move_cd=0
        self.dlg_npc=None;self.dlg_lines=[];self.dlg_page=0
        self.hit_fx=[];self.dmg_nums=[]
        self.levelup_timer=0;self.ch_announce=0
        self.trans_alpha=0;self.pending_trans=None;self.transitioning=False;self.entering_name=""
        self.inv_sel=0;self.inv_tab=0  # 0=esyalar 1=ekipman
        self.projectiles:List[Projectile]=[]

    def _start_game(self):
        st=self.temp_stats;st.hp=st.max_hp;st.mp=st.max_mp
        sx,sy=_snap(self.maps["ashveil"],29,25)
        self.player=Player(sx,sy,st)
        self.cur_key="ashveil";self.cur_map=self.maps["ashveil"];self.state="playing"

    def _cam(self):
        if not self.player: return
        self.cam_x=max(0,min(self.player.px-SW//2,self.cur_map.w*TILE-SW))
        self.cam_y=max(0,min(self.player.py-SH//2,self.cur_map.h*TILE-SH))

    def _try_move(self,dx,dy)->bool:
        p=self.player;ntx=p.tx+dx;nty=p.ty+dy
        if not self.cur_map.walkable(ntx,nty): return False
        for n in self.cur_map.npcs:
            if n.tx==ntx and n.ty==nty: return False
        for e in self.cur_map.enemies:
            if e.alive and e.tx==ntx and e.ty==nty: return False
        p.tx=ntx;p.ty=nty;p.px=ntx*TILE;p.py=nty*TILE
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
        p=self.player;p.tx=tx;p.ty=ty;p.px=tx*TILE;p.py=ty*TILE
        self.pending_trans=None;self.transitioning=False;self.trans_alpha=0
        self.projectiles.clear();self._check_ch()

    def _check_ch(self):
        ch=self.flags["ch"]
        if ch==2 and self.cur_key=="dark_forest": self._advance(3)
        if ch==5 and self.cur_key=="shadow_castle": self._advance(6)

    def _advance(self,ch):
        if self.flags["ch"]<ch: self.flags["ch"]=ch;self.ch_announce=260

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
            if is_crit and pr:
                self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":50,"col":UI_GD,"txt":"KRIT!"})
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

    def _hit(self,e,dmg,crit=False):
        if crit: dmg=int(dmg*1.8)
        e.hp-=dmg;e.hp=max(0,e.hp)
        col=UI_GD if crit else HP_R
        self.hit_fx.append({"x":e.px+TILE//2,"y":e.py+TILE//2,"f":0,"mf":20})
        self.dmg_nums.append({"x":e.px+TILE//2,"y":e.py,"v":dmg,"l":45,"col":col,"txt":"KRIT!" if crit else None})
        self.ps.emit_hit(e.px+TILE//2,e.py+TILE//2)
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
        if lv: self.levelup_timer=180
        if e.is_boss and e.kind=="malachar": self.flags["malachar_defeated"]=True;self.state="victory"

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
        if not st.can_use(slot): return
        ab=ABILITIES[st.char_class][slot];st.mp-=ab["mp"];st.ab_cds[slot]=ab["cd"]
        cx=p.px+TILE//2;cy=p.py+TILE//2
        d=p.direction;ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d,(0,1))
        aid=ab["id"]
        if aid=="shield_bash":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=1.8:
                    self._hit(e,int(st.attack*1.5))
                    nx2=e.tx+ox;ny2=e.ty+oy
                    if self.cur_map.walkable(nx2,ny2): e.tx=nx2;e.ty=ny2;e.px=nx2*TILE;e.py=ny2*TILE
            self.ps.emit_magic(cx,cy,col=(220,120,60))
        elif aid=="whirlwind":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=2.2: self._hit(e,int(st.attack*1.2))
            self.ps.emit(cx,cy,30,(200,150,60),6.0,40)
        elif aid=="war_cry":
            st.buffs["war_cry"]=180;self.ps.emit(cx,cy,25,(220,80,40),5.0,50)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":80,"col":(220,80,40),"txt":"SAVAS CIGLIK!"})
        elif aid=="earthquake":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.attack*2.0))
            for _ in range(40): self.ps.emit(cx+random.randint(-96,96),cy+random.randint(-96,96),5,(180,120,40),3.0,30)
        elif aid=="freeze":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.0:
                    e.frozen=max(e.frozen,120);self._hit(e,int(st.magic_atk*0.8))
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
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":100,"col":(180,180,255),"txt":"ZAMAN DUR!"})
        elif aid=="multi_shot":
            for ang in[-25,0,25]:
                rad=math.atan2(oy,ox)+math.radians(ang);self._proj(cx,cy,math.cos(rad),math.sin(rad),6,"arrow",int(st.attack*0.9))
        elif aid=="trap":
            t=Trap(p.tx+ox,p.ty+oy,int(st.attack*1.8));self.cur_map.traps.append(t)
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":60,"col":(180,140,60),"txt":"Tuzak!"})
        elif aid=="rain_arrows":
            for ang_d in range(0,360,45):
                rad=math.radians(ang_d);self._proj(cx,cy,math.cos(rad),math.sin(rad),5,"arrow",int(st.attack*0.8))
        elif aid=="shadow_step":
            for e in self.cur_map.enemies:
                if not e.alive: continue
                nx2=e.tx-ox;ny2=e.ty-oy
                if self.cur_map.walkable(nx2,ny2):
                    p.tx=nx2;p.ty=ny2;p.px=nx2*TILE;p.py=ny2*TILE;self._hit(e,int(st.attack*2.0))
                    self.ps.emit(cx,cy,20,(60,40,120),5.0,30);break
        elif aid=="mass_heal":
            amt=int(25+st.wis*2);st.heal(amt)
            self.ps.emit_magic(cx,cy,col=(80,220,120))
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":amt,"l":60,"col":HP_G,"txt":None})
        elif aid=="holy_shield":
            st.buffs["holy_shield"]=120;self.ps.emit_magic(cx,cy,col=(255,220,80))
            self.dmg_nums.append({"x":cx,"y":cy-TILE,"v":None,"l":60,"col":(255,220,60),"txt":"K.KALKAN!"})
        elif aid=="divine_storm":
            for e in self.cur_map.enemies:
                if e.alive and math.hypot(e.tx-p.tx,e.ty-p.ty)<=3.5: self._hit(e,int(st.magic_atk*1.8))
            for _ in range(30): self.ps.emit(cx+random.randint(-80,80),cy+random.randint(-80,80),6,(255,240,120),4.0,40)
        elif aid=="resurrection":
            st.heal(st.max_hp//2);st.restore_mp(st.max_mp//2)
            self.ps.emit(cx,cy,50,(255,200,100),6.0,70)
            self.dmg_nums.append({"x":cx,"y":cy-TILE*2,"v":None,"l":120,"col":(255,180,80),"txt":"DIRILIS!"})

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
                    self.ps.emit(tt.tx*TILE+TILE//2,tt.ty*TILE+TILE//2,20,(255,180,40),5.0,35);break
        self.cur_map.traps=[tt for tt in self.cur_map.traps if tt.active]

    def _update_enemies(self):
        p=self.player;ppx=p.px+TILE//2;ppy=p.py+TILE//2
        for e in self.cur_map.enemies:
            if not e.alive: continue
            if e.frozen>0: e.frozen-=1;continue
            ex=e.px+TILE//2;ey=e.py+TILE//2;dist=math.hypot(ex-ppx,ey-ppy)
            if dist<e.agro_range: e.state="chase"
            elif e.state=="chase" and dist>e.agro_range*1.5: e.state="idle"
            if e.state!="chase": continue
            e.move_cd-=1
            spd=max(6,20-p.stats.level*2)
            if e.kind in("wolf","ice_wolf"): spd=max(4,spd-4)
            if e.kind=="golem": spd+=8
            if e.move_cd<=0:
                e.move_cd=spd
                ddx=0 if e.tx==p.tx else(1 if p.tx>e.tx else -1)
                ddy=0 if e.ty==p.ty else(1 if p.ty>e.ty else -1)
                if abs(p.tx-e.tx)>=abs(p.ty-e.ty): ddy=0
                else: ddx=0
                nx2=e.tx+ddx;ny2=e.ty+ddy
                if(self.cur_map.walkable(nx2,ny2) and
                   not any(o.alive and o.tx==nx2 and o.ty==ny2 for o in self.cur_map.enemies if o is not e) and
                   not(nx2==p.tx and ny2==p.ty)):
                    e.tx=nx2;e.ty=ny2;e.px=nx2*TILE;e.py=ny2*TILE
            if abs(e.tx-p.tx)<=1 and abs(e.ty-p.ty)<=1 and p.invincible<=0:
                dmg=max(1,e.atk-p.stats.defense+random.randint(-2,3))
                if "holy_shield" in p.stats.buffs:
                    sh=p.stats.buffs["holy_shield"]
                    if isinstance(sh,int): p.stats.buffs["holy_shield"]=max(0,sh-dmg);dmg=0
                p.stats.hp-=dmg;p.stats.hp=max(0,p.stats.hp);p.invincible=40
                self.ps.emit_hit(ppx,ppy)
                self.dmg_nums.append({"x":ppx,"y":ppy-TILE//2,"v":dmg,"l":40,"col":HP_R})
                if p.stats.hp<=0: self.state="gameover"

    def _interact(self):
        p=self.player;d=p.direction
        ox,oy={"right":(1,0),"left":(-1,0),"up":(0,-1),"down":(0,1)}.get(d,(0,1))
        itx=p.tx+ox;ity=p.ty+oy
        for npc in self.cur_map.npcs:
            if npc.tx==itx and npc.ty==ity:
                lines=npc.get_dialog(self.flags);self.dlg_npc=npc;self.dlg_lines=lines;self.dlg_page=0;self.state="dialog"
                if npc.name=="Yasli Aldric" and not self.flags["speak_aldric"]:
                    self.flags["speak_aldric"]=True;self._advance(2)
                elif npc.name=="Oracle Nyx" and not self.flags.get("speak_oracle") and self.flags.get("earth_crystal"):
                    self.flags["speak_oracle"]=True;self._advance(5)
                return
        if(itx,ity) in self.cur_map.chests:
            loot=self.cur_map.chests.pop((itx,ity))
            for ik in loot:
                if ik=="gold": p.stats.gold+=ITEMS["gold"][3]
                elif ik in("earth_c","water_c"): p.quest_items.append(ik);self._quest_item(ik)
                else: p.inventory.append(ik)
            self.cur_map.set(itx,ity,T.FLOOR);self.ps.emit_gold(itx*TILE+TILE//2,ity*TILE+TILE//2)
            self.dmg_nums.append({"x":itx*TILE+TILE//2,"y":ity*TILE,"v":None,"l":70,"col":UI_GD,"txt":"Sandik Acildi!"})

    def _inv_use_item(self):
        """Envanterde seçili eşyayı kullan / ekipmanı giy."""
        p=self.player;u=list(dict.fromkeys(p.inventory))
        if not(0<=self.inv_sel<len(u)): return
        ik=u[self.inv_sel];itm=ALL_ITEMS.get(ik)
        if not itm: return
        typ=itm[2]
        if typ=="heal": p.stats.heal(itm[3]);p.inventory.remove(ik);self.ps.emit_magic(p.px+TILE//2,p.py)
        elif typ=="mana": p.stats.restore_mp(itm[3]);p.inventory.remove(ik)
        elif typ.startswith("stat_"): p.stats.apply_item(typ,itm[3]);p.inventory.remove(ik)
        elif typ=="equip":
            old=p.stats.equip(ik)
            if old=="":  # başarılı ekipleme, eski slot boştu
                p.inventory.remove(ik)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":f"Giyildi!"})
            elif old and old!=ik:  # eski ekipman çıkarıldı, envantera döndü
                p.inventory.remove(ik);p.inventory.append(old)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_GN,"txt":f"Degistirildi!"})
            elif old==ik:  # zaten ekipli, çıkar
                slot=EQUIP_ITEMS[ik][3];p.stats.unequip(slot)
                self.dmg_nums.append({"x":p.px+TILE//2,"y":p.py,"v":None,"l":60,"col":UI_RD,"txt":f"Cikarildi!"})

    # ── Ana Döngü ────────────────────────────────────────────────
    def run(self):
        running=True
        while running:
            self.tick=pygame.time.get_ticks();self.clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: running=False;break
                if ev.type==pygame.KEYDOWN:
                    k=ev.key
                    if k==pygame.K_F8:
                        pygame.image.save(self.screen, f"screenshot_{self.tick}.png")
                        print(f"Screenshot saved: screenshot_{self.tick}.png")
                    if self.state=="title":
                        if k in(pygame.K_RETURN,pygame.K_e): self.state="story"
                    elif self.state=="story":
                        if k==pygame.K_RETURN:
                            if self.story_shown<len(STORY_LINES): self.story_shown=len(STORY_LINES)
                            else: self.state="class_select"
                        elif k==pygame.K_SPACE: self.story_shown=min(self.story_shown+1,len(STORY_LINES))
                    elif self.state=="class_select":
                        ks=list(CLASS_INFO.keys())
                        if k in(pygame.K_LEFT,pygame.K_a): self.class_sel=max(0,self.class_sel-1)
                        elif k in(pygame.K_RIGHT,pygame.K_d): self.class_sel=min(len(ks)-1,self.class_sel+1)
                        elif k in(pygame.K_RETURN,pygame.K_e):
                            self.temp_stats=PlayerStats(ks[self.class_sel]);self.free_pts=10;self.stat_sel=0;self.is_lu=False;self.state="stat_alloc"
                    elif self.state=="stat_alloc":
                        st=self.temp_stats;sk_m=["str","int","agi","vit","wis"];sk=sk_m[self.stat_sel];rsk="int_" if sk=="int" else sk
                        if k in(pygame.K_UP,pygame.K_w): self.stat_sel=max(0,self.stat_sel-1)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.stat_sel=min(4,self.stat_sel+1)
                        elif k in(pygame.K_RIGHT,pygame.K_d):
                            if self.free_pts>0: setattr(st,rsk,getattr(st,rsk)+1);self.free_pts-=1
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            if getattr(st,rsk)>2: setattr(st,rsk,getattr(st,rsk)-1);self.free_pts+=1
                        elif k==pygame.K_RETURN:
                            if self.is_lu: self.player.stats.skill_points=0;self.state="playing"
                            else: self._start_game()
                    elif self.state=="dialog":
                        if k in(pygame.K_e,pygame.K_RETURN,pygame.K_SPACE):
                            self.dlg_page+=1
                            if self.dlg_page*4>=len(self.dlg_lines): self.state="playing"
                    elif self.state=="inventory":
                        u=list(dict.fromkeys(self.player.inventory))
                        if k==pygame.K_TAB: self.inv_tab=1-self.inv_tab
                        elif k in(pygame.K_LEFT,pygame.K_a): self.inv_sel=max(0,self.inv_sel-1)
                        elif k in(pygame.K_RIGHT,pygame.K_d): self.inv_sel=min(len(u)-1,self.inv_sel+1)
                        elif k in(pygame.K_UP,pygame.K_w): self.inv_sel=max(0,self.inv_sel-5)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.inv_sel=min(len(u)-1,self.inv_sel+5)
                        elif k==pygame.K_e:
                            if self.inv_tab==0: self._inv_use_item()
                            elif self.inv_tab==1:
                                # Ekipman sekmesinde slot seçili ekipmanı çıkar
                                slots=["weapon","armor","ring"];slot=slots[min(self.stat_sel,2)]
                                old=self.player.stats.unequip(slot)
                                if old: self.player.inventory.append(old)
                        elif k in(pygame.K_i,pygame.K_ESCAPE): self.state="playing"
                    elif self.state=="quest_log":
                        if k in(pygame.K_q,pygame.K_ESCAPE): self.state="playing"
                    elif self.state=="levelup_alloc":
                        st=self.player.stats;sk_m=["str","int","agi","vit","wis"];sk=sk_m[self.stat_sel];rsk="int_" if sk=="int" else sk;fp=st.skill_points
                        if k in(pygame.K_UP,pygame.K_w): self.stat_sel=max(0,self.stat_sel-1)
                        elif k in(pygame.K_DOWN,pygame.K_s): self.stat_sel=min(4,self.stat_sel+1)
                        elif k in(pygame.K_RIGHT,pygame.K_d):
                            if fp>0: setattr(st,rsk,min(30,getattr(st,rsk)+1));st.skill_points-=1
                        elif k in(pygame.K_LEFT,pygame.K_a):
                            if getattr(st,rsk)>2: setattr(st,rsk,getattr(st,rsk)-1);st.skill_points+=1
                        elif k==pygame.K_RETURN:
                            if st.skill_points==0: self.state="playing"
                    elif self.state=="gameover":
                        if k==pygame.K_r: self._reset()
                    elif self.state=="victory":
                        if k==pygame.K_ESCAPE: self._reset()
                    elif self.state=="playing":
                        if k==pygame.K_ESCAPE: running=False
                        elif k==pygame.K_i: self.inv_sel=0;self.inv_tab=0;self.state="inventory"
                        elif k==pygame.K_q: self.state="quest_log"
                        elif k==pygame.K_e: self._interact()
                        elif k==pygame.K_SPACE: self._auto_attack()
                        elif k in(pygame.K_1,pygame.K_KP1): self._use_ability(0)
                        elif k in(pygame.K_2,pygame.K_KP2): self._use_ability(1)
                        elif k in(pygame.K_3,pygame.K_KP3): self._use_ability(2)
                        elif k in(pygame.K_4,pygame.K_KP4): self._use_ability(3)
                        elif k==pygame.K_u:
                            if self.player and self.player.stats.skill_points>0:
                                self.stat_sel=0;self.temp_stats=self.player.stats;self.is_lu=True;self.state="levelup_alloc"

            if self.state=="story":
                self.story_timer+=1
                if self.story_timer%35==0: self.story_shown=min(self.story_shown+1,len(STORY_LINES))

            if self.state=="playing" and self.player:
                p=self.player;keys=pygame.key.get_pressed();any_d=False
                if keys[pygame.K_LEFT] or keys[pygame.K_a]: p.direction="left";any_d=True
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]: p.direction="right";any_d=True
                elif keys[pygame.K_UP] or keys[pygame.K_w]: p.direction="up";any_d=True
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]: p.direction="down";any_d=True
                if self.move_cd>0: self.move_cd-=1
                if any_d and self.move_cd==0 and not self.transitioning:
                    dx3={"left":-1,"right":1,"up":0,"down":0}[p.direction]
                    dy3={"left":0,"right":0,"up":-1,"down":1}[p.direction]
                    if self._try_move(dx3,dy3): p.frame+=1
                    self.move_cd=p.stats.move_delay
                if p.invincible>0: p.invincible-=1
                if p.attacking: p.atk_frame+=1
                if p.atk_frame>=p.atk_max: p.attacking=False
                p.stats.tick_cds();p.stats.tick_buffs()
                if p.stats.char_class=="healer" and self.tick%120==0:
                    if p.stats.hp<p.stats.max_hp and p.stats.mp>=3: p.stats.heal(2);p.stats.mp-=3
                if self.levelup_timer>0: self.levelup_timer-=1
                if self.ch_announce>0: self.ch_announce-=1
                self._update_enemies();self._update_projs();self._update_traps()
                if self.levelup_timer==100 and p.stats.skill_points>0:
                    self.stat_sel=0;self.temp_stats=p.stats;self.is_lu=True;self.state="levelup_alloc"

            if self.transitioning and self.pending_trans:
                self.trans_alpha=min(255,self.trans_alpha+10)
                if self.trans_alpha>=255: self._finish_trans()
            elif self.trans_alpha>0: self.trans_alpha=max(0,self.trans_alpha-10)

            self.ps.update();self._cam()

            # ─── Çizim ───────────────────────────────────────────
            self.screen.fill(DKG)
            if self.state=="title": self.ui.draw_title(self.screen,self.tick)
            elif self.state=="story": self.ui.draw_story(self.screen,self.story_shown,self.tick)
            elif self.state=="class_select": self.ui.draw_class_select(self.screen,self.class_sel,self.tick)
            elif self.state=="stat_alloc": self.ui.draw_stat_alloc(self.screen,self.temp_stats,self.free_pts,self.stat_sel,False,self.tick)
            else:
                if self.cur_map: self.cur_map.draw(self.screen,self.cam_x,self.cam_y,self.tick)
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
                    if self.state in("playing","dialog","inventory","quest_log","levelup_alloc"):
                        cq=QUESTS.get(self.flags["ch"],("",""))[0]
                        self.ui.draw_hud(self.screen,p,self.cur_map.name,self.flags["ch"],cq,self.tick)
                        self.ui.draw_ability_bar(self.screen,p.stats,self.tick)
                    if self.levelup_timer>0: self.ui.draw_levelup_popup(self.screen,p.stats.level,self.tick)
                    if self.ch_announce>0: self.ui.draw_chapter(self.screen,self.flags["ch"],min(255,self.ch_announce*3))

                if self.state=="dialog":
                    lpp=4;pl=self.dlg_lines[self.dlg_page*lpp:(self.dlg_page+1)*lpp]
                    total=(len(self.dlg_lines)+lpp-1)//lpp
                    self.ui.draw_dialog(self.screen,self.dlg_npc.name if self.dlg_npc else "?",pl,self.dlg_page+1,total)
                elif self.state=="inventory":
                    self.ui.draw_inventory(self.screen,self.player,self.inv_sel,self.inv_tab,self.tick)
                elif self.state=="quest_log":
                    self.ui.draw_quest_log(self.screen,self.flags,self.flags["ch"])
                elif self.state=="levelup_alloc":
                    self.ui.draw_stat_alloc(self.screen,self.player.stats,self.player.stats.skill_points,self.stat_sel,True,self.tick)
                elif self.state=="gameover":
                    self.ui.draw_gameover(self.screen)
                elif self.state=="victory":
                    self.ui.draw_victory(self.screen,self.tick)

            if self.trans_alpha>0: self.ui.draw_transition(self.screen,self.trans_alpha,self.entering_name)
            pygame.display.flip()

        pygame.quit();sys.exit()


if __name__=="__main__":
    print("="*56)
    print("  KARANLIK TAÇ'IN LANETİ  v4.0")
    print("  pip install pygame  |  python pixel_rpg.py")
    print("  Yeni: Sinifa ozgun saldiri | Ekipman Sistemi")
    print("  Yeni: Gorunmez harita gecisleri | Genis orman")
    print("="*56)
    Game().run()
