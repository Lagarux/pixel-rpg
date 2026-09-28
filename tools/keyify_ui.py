#!/usr/bin/env python3
"""
Arayuzde gomulu kalan Turkce metinleri T_() anahtarlarina cevirir.

Acik eslestirme listesiyle calisir (regex tahmini degil): her degisiklik
bilincli. Yazmadan once ast.parse ile dogrular.
"""
import ast
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "pixel_rpg.py")
LOC = os.path.join(ROOT, "assets", "locales", "tr.json")

# (kodda gecen tam metin, anahtar, Turkce karsiligi)
# Metin zaten LOC'ta varsa Turkce karsiligi None birakilir.
PLAIN = [
    ('"SEVIYE ATLADI!"',                                     "stat_levelup",     None),
    ('"NITELIK DAGITIMI"',                                   "stat_alloc",       None),
    ('"[Yon]Sec  [</> ]Degistir  [ENTER]Onayla"',             "ui.stat_keys",     "[Yon]Sec  [</> ]Degistir  [ENTER]Onayla"),
    ('"[</> ] Sec   [E/ENTER] Onayla"',                       "class_confirm",    None),
    ('"[ ENTER ] Devam"',                                     "ui.story_next",    "[ ENTER ] Devam"),
    ('"[ C ]  Devam Et"',                                     "ui.title_continue","[ C ]  Devam Et"),
    ('"[U] Nitelik puan dagit!"',                             "ui.levelup_hint",  "[U] Nitelik puani dagit!"),
    ('"[ R ] Yeniden Basla"',                                 "gameover_restart", None),
    ('"[ ESC ] Ana Menu"',                                    "victory_menu",     None),
    ('"Ekipman Bonusu:"',                                     "ui.equip_bonus",   "Ekipman Bonusu:"),
    ('"[Tab]Sekme  [I/ESC]Kapat  [Yon]Sec  [E]Kullan/Giy"',   "ui.inv_keys_items","[Tab] Ekipman Sekmesi   [Yon]Sec   [E]Kullan/Giy   [I/ESC]Kapat"),
    ('"[Tab]Sekme  [I/ESC]Kapat  [Yukari/Asagi]Yuva Sec  [E]Cikar"', "ui.inv_keys_gear", "[Tab] Esya Sekmesi   [Yukari/Asagi]Yuva Sec   [E]Cikar   [I/ESC]Kapat"),
    ('"[ DEVAM ]"',                                           "ui.pause_resume",  "[ DEVAM ]"),
    ('"[ KAYDET ]"',                                          "ui.pause_save",    "[ KAYDET ]"),
    ('"[ AYARLAR ]"',                                         "ui.pause_settings","[ AYARLAR ]"),
    ('"[ ANA MENU ]"',                                        "ui.pause_menu",    "[ ANA MENU ]"),
    ('"[ CIKIS ]"',                                           "ui.pause_quit",    "[ CIKIS ]"),
    ('"OYUN DURAKLATILDI"',                                   "ui.paused",        "OYUN DURAKLATILDI"),
    ('"Parşömen Avı"',                                        "ui.sq_scroll",     "Parşömen Avı"),
    ('"Domuz Avı"',                                           "ui.sq_boar",       "Domuz Avı"),
    ('"Balıkçı Yardımı"',                                     "ui.sq_fish",       "Balıkçı Yardımı"),
    ('"Tamamlandı!"',                                         "ui.completed",     "Tamamlandı!"),
    ('"Riva ile konuş"',                                      "ui.sq_fish_short", "Riva ile konuş"),
    ('"Yan Görevler"',                                        "ui.side_quests",   "Yan Görevler"),
    ('"─── YAN GÖREVLER ───"',                                "ui.side_quests_hdr","─── YAN GÖREVLER ───"),
    ('"Gizemli Kütüphane: 3 parşömen bul"',                   "ui.sq_scroll_desc","Gizemli Kütüphane: 3 parşömen bul"),
    ('"Güney Çayırı: 3 domuz öldür"',                         "ui.sq_boar_desc",  "Güney Çayırı: 3 domuz öldür"),
    ('"Batı Nehri: Riva ile konuş"',                          "ui.sq_fish_desc",  "Batı Nehri: Riva ile konuş"),
    ('"[Q/ESC] Kapat"',                                       "ui.close_quests",  "[Q/ESC] Kapat"),
    ('"SAVAŞ ÇIĞLIĞI"',                                       "ui.buff_war_cry",  "SAVAŞ ÇIĞLIĞI"),
    ('"KUTSAL KALKAN"',                                       "ui.buff_holy",     "KUTSAL KALKAN"),
    ('"KRIT!"',                                               "ui.crit",          "KRIT!"),
    ('"SAVAS CIGLIK!"',                                       "ui.shout_war_cry", "SAVAŞ ÇIĞLIĞI!"),
    ('"ZAMAN DUR!"',                                          "ui.shout_time",    "ZAMAN DURDU!"),
    ('"K.KALKAN!"',                                           "ui.shout_shield",  "KUTSAL KALKAN!"),
    ('"DIRILIS!"',                                            "ui.shout_resurrect","DİRİLİŞ!"),
    ('"Tuzak!"',                                              "ui.trap_set",      "Tuzak kuruldu!"),
    ('"Yan Görev Tamamlandi!"',                               "ui.sq_done",       "Yan Görev Tamamlandı!"),
    ('"Kutuphaneciye götür!"',                                "ui.take_librarian","Kütüphaneciye götür!"),
    ('"Sandik Acildi!"',                                      "chest_opened",     None),
    ('"Kaydedildi"',                                          "ui.saved",         "Kaydedildi"),
    ('"Kaydedilemedi!"',                                      "ui.save_failed",   "Kaydedilemedi!"),
    ('"GUC"',                                                 "ui.abbr_str",      "GUC"),
    ('"ZEKA"',                                                "ui.abbr_int",      "ZEKA"),
    ('"CEV"',                                                 "ui.abbr_agi",      "CEV"),
    ('"DAY"',                                                 "ui.abbr_vit",      "DAY"),
    ('"BIL"',                                                 "ui.abbr_wis",      "BIL"),
    ('"[WASD]Hareket"',                                       "ui.key_move",      "[WASD]Hareket"),
    ('"[E]Konuş/Aç"',                                         "ui.key_interact",  "[E]Konuş/Aç"),
    ('"[Spc]Saldırı"',                                        "ui.key_attack",    "[Spc]Saldırı"),
    ('"[1-4]Yetenek"',                                        "ui.key_ability",   "[1-4]Yetenek"),
    ('"[I]Envanter"',                                         "ui.key_inventory", "[I]Envanter"),
    ('"[Q]Görev"',                                            "ui.key_quests",    "[Q]Görev"),
    ('"[F1]Ayarlar"',                                         "ui.key_settings",  "[F1]Ayarlar"),
    ('"[F11]TamEkran"',                                       "ui.key_fullscreen","[F11]TamEkran"),
    ('"Karanlik seni yuttu..."',                              "gameover_sub",     None),
    ('"— Bos —"',                                             "slot_empty",       "— Boş —"),
    ('"Esya sekmesinden ekipman giy"',                        "slot_hint",        "Eşya sekmesinden giy"),
    ('"Giyildi!"',                                            "ui.equipped_msg",  "Giyildi!"),
    ('"Degistirildi!"',                                       "ui.swapped_msg",   "Değiştirildi!"),
    ('"Cikarildi!"',                                          "ui.removed_msg",   "Çıkarıldı!"),
    ('"Parsomen Bulundu!"',                                   "ui.scroll_found",  "Parşömen Bulundu!"),
]

# Yuva adlari
SLOTS = {"weapon": "Silah", "armor": "Zırh", "boots": "Bot", "ring": "Yüzük", "amulet": "Muska"}

# f-string / ozel durumlar: (eski, yeni)
SPECIAL = [
    # Sinif secimi: saldiri adi
    ("""self.txt(surf,f"Sld:{ci['atk_name'][:12]}",cx2+6,cy2+96""",
     """self.txt(surf,T_("ui.atk_prefix")+class_text(k,"atk_name")[:12],cx2+6,cy2+96"""),
    # Sinif adi ve lore
    ("""nm=self.fmd.render(ci["name"],True,cc if sel_this else LGR)""",
     """nm=self.fmd.render(class_text(k,"name"),True,cc if sel_this else LGR)"""),
    ("""for li,ln in enumerate(ci["lore"].split("\\n")):""",
     """for li,ln in enumerate(class_text(k,"lore").split("\\n")):"""),
    # Nitelik ekrani
    ("""self.txt(surf,sname,px+20,sy2+6,sc2,self.fmd)""",
     """self.txt(surf,stat_name(sk),px+20,sy2+6,sc2,self.fmd)"""),
    ("""self.txt(surf,STAT_DESCS[sk],px+20,sy2+26,GR,self.fsm)""",
     """self.txt(surf,stat_desc(sk),px+20,sy2+26,GR,self.fsm)"""),
    # Seviye atlama penceresi
    ('''tt=self.flg.render(f"SEVIYE {level} !",True,UI_GD)''',
     '''tt=self.flg.render(T_("ui.level_up_n",level),True,UI_GD)'''),
    # Hikaye satirlari
    ("""for i,(line,col) in enumerate(STORY_LINES[:lines_shown]):""",
     """for i,(line,col) in enumerate(STORY_LINES[:lines_shown]):\n            line=T_("story.%d"%(i+1),default=line) if line.strip() else line"""),
    # Basliktaki alt yazi
    ('''f"v{VERSION} — Sinifa Ozgun Saldiri | Ekipman Sistemi"''',
     '''"v%s — %s"%(VERSION,T_("ui.tagline"))'''),
    # Bolum duyurusu
    ("""t2=self.flg.render(QUESTS[chapter][0],True,UI_AC)""",
     """t2=self.flg.render(quest_title(chapter),True,UI_AC)"""),
    # Yetenek cubugu
    ("""self.txt(surf,ab["name"][:7],sx+1,sy+36,c2,self.fsm,shadow=False)""",
     """self.txt(surf,ability_name(ab)[:7],sx+1,sy+36,c2,self.fsm,shadow=False)"""),
    # HUD: sinif adi
    ('''self.txt(surf,f"{ci['name']}  {T_('lvl')}{st.level}"''',
     '''self.txt(surf,f"{class_text(st.char_class,'name')}  {T_('lvl')}{st.level}"'''),
    # HUD: saldiri adi
    ("""atk_name=CLASS_INFO[st.char_class]["atk_name"]""",
     """atk_name=class_text(st.char_class,"atk_name")"""),
    # Envanter: esya adi ve aciklamasi
    ("""self.txt(surf,itm[0][:10],ix+4,iy+52,WH,self.fsm)""",
     """self.txt(surf,item_name(k)[:10],ix+4,iy+52,WH,self.fsm)"""),
    ("""self.txt(surf,si[0],px+14,py+ph-62,UI_AC,self.fmd)""",
     """self.txt(surf,item_name(all_keys[sel]),px+14,py+ph-62,UI_AC,self.fmd)"""),
    ("""self.txt(surf,si[4],px+14,py+ph-44,LGR,self.fss)""",
     """self.txt(surf,item_desc(all_keys[sel]),px+14,py+ph-44,LGR,self.fss)"""),
    # Gorev gunlugu: bolum satirlari
    ('''self.txt(surf,f"[✓] Bölüm {ch}: {qname}"''',
     '''self.txt(surf,f"[✓] {T_('chapter_label')} {ch}: {quest_title(ch)}"'''),
    ('''self.txt(surf,f"[►] Bölüm {ch}: {qname}"''',
     '''self.txt(surf,f"[►] {T_('chapter_label')} {ch}: {quest_title(ch)}"'''),
    ('''self.txt(surf,f"    {qdesc}"''',
     '''self.txt(surf,f"    {quest_desc(ch)}"'''),
    ('''self.txt(surf,f"[?] Bölüm {ch}: ???"''',
     '''self.txt(surf,f"[?] {T_('chapter_label')} {ch}: ???"'''),
    # NPC kimlik karsilastirmalari artik anahtar uzerinden
    ('''if npc.name=="Yasli Aldric"''', '''if npc.name=="npc.yasli_aldric"'''),
    ('''elif npc.name=="Oracle Nyx"''', '''elif npc.name=="npc.oracle_nyx"'''),
    ('''elif npc.name=="Balikci Riva"''', '''elif npc.name=="npc.balikci_riva"'''),
    # Harita ve NPC adlari ekranda cevrilir
    ("""self.ui.draw_hud(self.screen,p,self.cur_map.name,""",
     """self.ui.draw_hud(self.screen,p,T_(self.cur_map.name),"""),
    ("""cq=QUESTS.get(self.flags["ch"],("",""))[0]""",
     """cq=quest_title(self.flags["ch"])"""),
    ("""self.ui.draw_transition(self.screen,self.trans_alpha,self.entering_name)""",
     """self.ui.draw_transition(self.screen,self.trans_alpha,T_(self.entering_name))"""),
    ('''self.ui.draw_dialog(self.screen,self.dlg_npc.name if self.dlg_npc else "?",pl,''',
     '''self.ui.draw_dialog(self.screen,T_(self.dlg_npc.name) if self.dlg_npc else "?",pl,'''),
    # Diyalog satirlari ceviriden gecsin
    ("""lpp=4;pl=self.dlg_lines[self.dlg_page*lpp:(self.dlg_page+1)*lpp]""",
     """lpp=4;pl=[dlg_line(e) for e in self.dlg_lines[self.dlg_page*lpp:(self.dlg_page+1)*lpp]]"""),
    # NPC etiketi
    ("""tag=_tag_surf(self.name)""", """tag=_tag_surf(T_(self.name))"""),
    # Kutuphaneci: sayac yeniden baglandi
    ('''return [f"dlg.libr.4",f"dlg.libr.5","dlg.libr.6"]''',
     '''return ["dlg.libr.4",("dlg.libr.5",n),"dlg.libr.6"]'''),
]


def main():
    s = io.open(SRC, encoding="utf-8").read()
    loc = json.load(io.open(LOC, encoding="utf-8"))
    missing = []

    for old, new in SPECIAL:
        if old not in s:
            missing.append(old[:60])
            continue
        s = s.replace(old, new, 1)

    for literal, key, tr in PLAIN:
        if literal not in s:
            missing.append(literal[:60])
            continue
        s = s.replace(literal, 'T_("%s")' % key)
        if tr is not None:
            loc.setdefault(key, tr)

    for slot, name in SLOTS.items():
        loc.setdefault("slot_" + slot, name)
    loc.setdefault("ui.atk_prefix", "Sld:")
    loc.setdefault("ui.level_up_n", "SEVIYE %d !")
    loc.setdefault("ui.tagline", "Sinifa Ozgun Saldiri | Ekipman Sistemi")
    loc["dlg.libr.5"] = "3 parşömen kayboldu! (%d/3 bulundu)"

    ast.parse(s)
    io.open(SRC, "w", encoding="utf-8").write(s)
    json.dump(loc, io.open(LOC, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("degistirilen:", len(PLAIN) + len(SPECIAL) - len(missing), "/", len(PLAIN) + len(SPECIAL))
    print("toplam anahtar:", len(loc))
    if missing:
        print("BULUNAMAYAN (%d):" % len(missing))
        for m in missing:
            print("   ", m)


if __name__ == "__main__":
    main()
