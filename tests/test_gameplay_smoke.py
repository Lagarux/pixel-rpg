#!/usr/bin/env python3
"""
Oyunu bastan sona otomatik oynatan duman (smoke) testi + ekran goruntusu uretimi.

Ne yapar:
  * Baslik -> hikaye -> sinif secimi -> nitelik dagitimi -> oyun akisini surer,
  * hareket, saldiri, yetenek, diyalog, sandik, envanter, gorev gunlugu,
    ayarlar, pause, harita gecisi, olum ve zafer ekranlarini gezer,
  * her adimda tests/screenshots/ altina PNG kaydeder,
  * hareket akiciligi ve kare basina SysFont cagrisi gibi olcumleri raporlar.

Calistirmak icin:
    python -m unittest discover -s tests            (tum testler)
    python tests/test_gameplay_smoke.py             (olcum raporu ile birlikte)
"""
import os
import unittest

import pygame

from harness import (
    Harness,
    SHOT_DIR,
    face_first_chest,
    face_first_enemy,
    face_first_npc,
    goto_map,
    load_game_module,
    mark,
    place_in_open_area,
)

def _set_state(name):
    def _s(game):
        game.state = name
    _s.__name__ = f"set_state_{name}"
    return _s


def _trigger_levelup(game):
    game.levelup_timer = 179
    game.player.stats.level = 3


def _start_transition(game):
    game._start_trans("village_dungeon", 10, 10)


def _assert_playing(game):
    assert game.state == "playing", f"oyun durumuna girilemedi: {game.state}"


def _spy_overlays(game):
    """Bilgi pencerelerinin hangi oyun durumunda cizildigini kaydeder (B3)."""
    for name in ("draw_levelup_popup", "draw_chapter", "draw_ability_bar"):
        orig = getattr(game.ui, name)

        def make(fn, key):
            def spy(*a, **k):
                _spy_overlays.seen.setdefault(key, set()).add(game.state)
                return fn(*a, **k)
            return spy

        setattr(game.ui, name, make(orig, name))


_spy_overlays.seen = {}


def _equip_two_items(game):
    """Ekipman sekmesi testi icin silah + zirh giydirir (B2)."""
    st = game.player.stats
    st.equipment["weapon"] = "iron_sword"
    st.equipment["armor"] = "plate_mail"
    st.equipment["ring"] = "power_ring"


def _record_equipment(game):
    _record_equipment.result = dict(game.player.stats.equipment)


_record_equipment.result = None


def _setup_healer_regen(game):
    """Sifaci pasif yenilenmesi olcumu icin guvenli bir kareye yerlestirir (B1)."""
    st = game.player.stats
    st.char_class = "healer"
    st.wis = 6
    st.hp = st.max_hp - 20
    st.mp = st.max_mp
    _setup_healer_regen.hp_before = st.hp


_setup_healer_regen.hp_before = None


def _record_healer_hp(game):
    _record_healer_hp.hp_after = game.player.stats.hp


_record_healer_hp.hp_after = None


class TestGameplaySmoke(unittest.TestCase):
    """Tek bir otomatik oturumda tum ekranlari gezer; cokme olmamali."""

    metrics = {}

    @classmethod
    def setUpClass(cls):
        mod = load_game_module()
        h = Harness(mod)
        script = [
            # ── Menuler ──────────────────────────────────────────
            h.do(_spy_overlays),
            h.wait(4), h.shot("01_baslik"),
            h.key(pygame.K_RETURN),            # -> hikaye
            h.wait(30),
            h.key(pygame.K_RETURN),            # tum satirlari goster
            h.wait(4), h.shot("02_hikaye"),
            h.key(pygame.K_RETURN),            # -> sinif secimi
            h.wait(4), h.shot("03_sinif_secimi"),
            h.key(pygame.K_RETURN),            # -> nitelik dagitimi
            h.wait(4),
        ]
        # 10 serbest puani dagit
        script += [h.key(pygame.K_RIGHT, wait=1) for _ in range(10)]
        script += [
            h.shot("04_nitelik_dagitimi"),
            h.key(pygame.K_RETURN),            # -> oyun basliyor (Ashveil)
            h.wait(10), h.shot("05_koy_ashveil"),

            # ── Hareket (acik alanda olculur) ────────────────────
            h.do(place_in_open_area), h.wait(2),
            h.do(mark("yuru_basla")),
            h.hold([pygame.K_DOWN], 40),
            h.do(mark("yuru_bitti")), h.release(),
            h.wait(2), h.shot("06_hareket_asagi"),
            h.hold([pygame.K_RIGHT], 24), h.release(),
            h.wait(2), h.shot("07_hareket_saga"),
            # Capraz hareket: acik alanda, iki eksen de degismeli
            h.do(place_in_open_area), h.wait(2), h.do(_record_diag_start),
            h.hold([pygame.K_DOWN, pygame.K_RIGHT], 40), h.release(), h.wait(2),
            h.do(_record_diagonal), h.shot("08_capraz_hareket"),

            # ── Etkilesim: NPC diyalogu ──────────────────────────
            h.do(face_first_npc), h.wait(2),
            h.key(pygame.K_e), h.wait(4), h.shot("09_diyalog"),
            h.key(pygame.K_e), h.wait(3),
            h.key(pygame.K_e), h.wait(3),
            h.key(pygame.K_ESCAPE), h.wait(3),

            # ── Etkilesim: sandik ────────────────────────────────
            h.do(face_first_chest), h.wait(2),
            h.key(pygame.K_e), h.wait(4), h.shot("10_sandik"),

            # ── Menuler (oyun ici) ───────────────────────────────
            h.key(pygame.K_i), h.wait(4), h.shot("11_envanter"),
            h.do(_equip_two_items),
            h.key(pygame.K_TAB), h.wait(3), h.shot("12_ekipman_sekmesi"),
            # Imleci "zirh" yuvasina indir ve cikar: dogru yuva bosalmali (B2)
            h.key(pygame.K_DOWN), h.wait(2), h.shot("12b_ekipman_imleci"),
            h.key(pygame.K_e), h.wait(3),
            h.do(_record_equipment),
            h.key(pygame.K_i), h.wait(3),
            h.key(pygame.K_q), h.wait(4), h.shot("13_gorev_gunlugu"),
            h.key(pygame.K_q), h.wait(3),
            h.key(pygame.K_F1), h.wait(4), h.shot("14_ayarlar"),
            h.key(pygame.K_ESCAPE), h.wait(3),
            h.key(pygame.K_ESCAPE), h.wait(4), h.shot("15_pause"),
            h.key(pygame.K_ESCAPE), h.wait(3),

            # ── Harita gecisi (fade) ─────────────────────────────
            h.do(_start_transition), h.wait(12), h.shot("16_harita_gecisi"),
            h.wait(30), h.shot("17_zindan"),

            # ── Savas ────────────────────────────────────────────
            h.do(goto_map("dark_forest")), h.do(face_first_enemy), h.wait(4),
            h.shot("18_savas_oncesi"),
            h.key(pygame.K_SPACE), h.wait(6), h.shot("19_saldiri"),
            h.key(pygame.K_1), h.wait(6), h.shot("20_yetenek"),
            h.wait(90), h.shot("21_dusman_yapay_zeka"),

            # ── Sifaci pasif yenilenmesi (B1) ────────────────────
            h.do(goto_map("ashveil")), h.do(_setup_healer_regen),
            h.wait(140), h.do(_record_healer_hp),

            # ── Seviye atlama / olum / zafer ─────────────────────
            h.do(goto_map("dark_forest")),
            h.do(_trigger_levelup), h.wait(4), h.shot("22_seviye_atladi"),
            h.wait(60),
            h.do(_set_state("gameover")), h.wait(4), h.shot("23_olum"),
            h.do(_set_state("victory")), h.wait(4), h.shot("24_zafer"),
        ]
        h.run(script, trace=True)
        cls.h = h
        cls.mod = mod

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_no_helper_errors(self):
        self.assertEqual(self.h.errors, [], "senaryo yardimcilari hata verdi")

    def test_all_screenshots_written(self):
        self.assertGreaterEqual(len(self.h.shots), 24)
        for path in self.h.shots:
            with self.subTest(shot=os.path.basename(path)):
                self.assertTrue(os.path.isfile(path), f"{path} yok")
                self.assertGreater(os.path.getsize(path), 2000, f"{path} bos gorunuyor")

    def test_game_reached_playing_state(self):
        self.assertIsNotNone(self.h.game.player, "oyuncu olusturulmadi")
        self.assertGreater(len(self.h.pos_trace), 100, "oyun durumunda yeterli kare gecmedi")

    def test_player_actually_moved(self):
        xs = {p[1] for p in self.h.pos_trace}
        ys = {p[2] for p in self.h.pos_trace}
        self.assertGreater(len(xs) + len(ys), 4, "oyuncu hic hareket etmedi")

    # ── Faz 1 regresyon testleri ─────────────────────────────────
    def test_levelup_popup_not_drawn_over_endgame_screens(self):
        """B3: seviye atlama penceresi olum/zafer ekranini kapatmamali."""
        seen = _spy_overlays.seen.get("draw_levelup_popup", set())
        self.assertTrue(seen, "seviye atlama penceresi hic cizilmedi -- senaryo bozulmus")
        self.assertFalse(
            seen & {"gameover", "victory"},
            f"seviye penceresi su durumlarda cizildi: {sorted(seen)}",
        )

    def test_chapter_banner_not_drawn_over_endgame_screens(self):
        """B3: bolum duyurusu da olum/zafer ekraninin ustune binmemeli."""
        seen = _spy_overlays.seen.get("draw_chapter", set())
        self.assertFalse(seen & {"gameover", "victory"}, f"bolum duyurusu: {sorted(seen)}")

    def test_ability_bar_hidden_during_dialog(self):
        """E6: diyalog kutusu alt seridi kapliyor, yetenek cubugu gizlenmeli."""
        seen = _spy_overlays.seen.get("draw_ability_bar", set())
        self.assertIn("playing", seen, "yetenek cubugu hic cizilmedi")
        self.assertNotIn("dialog", seen, "yetenek cubugu diyalog kutusuyla cakisiyor")

    def test_equipment_tab_unequips_selected_slot(self):
        """B2: ekipman sekmesinde imlec hangi yuvadaysa o cikarilmali."""
        eq = _record_equipment.result
        self.assertIsNotNone(eq, "ekipman durumu kaydedilemedi")
        self.assertIsNone(eq["armor"], "imlec zirhtayken zirh cikarilmadi")
        self.assertEqual(eq["weapon"], "iron_sword", "yanlis yuva cikarildi (silah)")
        self.assertEqual(eq["ring"], "power_ring", "yanlis yuva cikarildi (yuzuk)")

    def test_healer_passive_regen_works(self):
        """B1: sifaci pasif yenilenmesi kare sayacina baglandi, duzenli calismali."""
        before = _setup_healer_regen.hp_before
        after = _record_healer_hp.hp_after
        self.assertIsNotNone(after, "sifaci HP olcumu alinamadi")
        self.assertGreater(after, before, "140 karede pasif yenilenme hic tetiklenmedi")

    # ── Faz 2 akicilik testleri ──────────────────────────────────
    def _walk_window(self):
        a = self.h.marks.get("yuru_basla")
        b = self.h.marks.get("yuru_bitti")
        self.assertIsNotNone(a, "yuruyus penceresi isaretlenmedi")
        return [p for p in self.h.pos_trace if a <= p[0] <= b]

    def test_player_never_teleports_between_frames(self):
        """A1: tek karede bir tile'lik sicrama olmamali (eskiden her adim 32 px'ti)."""
        tile = self.mod.TILE
        window = self._walk_window()
        steps = [abs(b[1] - a[1]) + abs(b[2] - a[2]) for a, b in zip(window, window[1:])]
        worst = max(steps) if steps else 0
        self.assertLess(worst, tile / 2, f"tek karede {worst:.1f} px atladi -- hareket isinlaniyor")

    def test_movement_is_continuous(self):
        """A1: yon tusu basiliyken karelerin buyuk cogunlugunda konum degismeli."""
        window = self._walk_window()
        self.assertGreater(len(window), 20, "yuruyus penceresi cok kisa")
        moved = sum(1 for a, b in zip(window, window[1:]) if (a[1], a[2]) != (b[1], b[2]))
        ratio = moved / (len(window) - 1)
        self.assertGreater(ratio, 0.8, f"karelerin yalnizca %{ratio*100:.0f}'inde hareket var")

    def test_camera_follows_smoothly(self):
        """A2: kamera da kare kare kaymali, 32 px'lik bloklar halinde degil."""
        tile = self.mod.TILE
        window = self._walk_window()
        steps = [d for d in (abs(b[3] - a[3]) + abs(b[4] - a[4]) for a, b in zip(window, window[1:])) if d]
        self.assertGreater(len(steps), 10, "kamera oyuncuyu takip etmiyor")
        self.assertLess(max(steps), tile / 2, f"kamera blok blok zipliyor (en buyuk {max(steps)} px)")

    def test_diagonal_movement_works(self):
        """A3: asagi+saga birlikte basiliyken iki eksen de ilerlemeli."""
        start = _record_diag_start.pos
        end = _record_diagonal.result
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertGreater(end[0], start[0], "capraz basiliyken yatay eksen ilerlemedi")
        self.assertGreater(end[1], start[1], "capraz basiliyken dikey eksen ilerlemedi")

    def test_no_frame_took_absurdly_long(self):
        """Tek bir karenin 250 ms'yi asmasi takilma (hitch) belirtisidir."""
        worst = max(self.h.frame_times[1:]) if len(self.h.frame_times) > 1 else 0
        self.assertLess(worst, 250.0, f"en kotu kare {worst:.1f} ms surdu")


class TestPerformanceProbe(unittest.TestCase):
    """FPS sinirini kaldirip ham mantik+cizim maliyetini olcer."""

    @classmethod
    def setUpClass(cls):
        mod = load_game_module("pixel_rpg_perf")
        h = Harness(mod, shot_prefix="perf_")
        script = [
            h.wait(2),
            h.key(pygame.K_RETURN), h.wait(4),    # baslik -> hikaye
            h.key(pygame.K_RETURN), h.wait(4),    # hikayeyi atla
            h.key(pygame.K_RETURN), h.wait(4),    # -> sinif secimi
            h.key(pygame.K_RETURN), h.wait(4),    # -> nitelik dagitimi
            h.key(pygame.K_RETURN), h.wait(20),   # -> oyun (Ashveil)
            h.do(_assert_playing),
            h.wait(240),                          # koyde 240 kare olc
            h.shot("koy_240_kare"),
        ]
        h.run(script, unlimited_fps=True)
        cls.h = h

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_reports_headroom(self):
        times = self.h.frame_times[-200:]
        self.assertTrue(times, "kare suresi olculemedi")
        avg = sum(times) / len(times)
        fps = 1000.0 / avg if avg else 0
        TestGameplaySmoke.metrics["avg_ms"] = avg
        TestGameplaySmoke.metrics["headroom_fps"] = fps
        # 60 FPS icin kare basina 16.7 ms butce var; en az iki kat pay bekliyoruz.
        self.assertLess(avg, 8.3, f"kare maliyeti {avg:.2f} ms -- 60 FPS icin pay cok dusuk")

    def test_reports_sysfont_per_frame(self):
        calls = self.h.sysfont_calls[-200:]
        avg = sum(calls) / len(calls) if calls else 0
        TestGameplaySmoke.metrics["sysfont_per_frame"] = avg
        # Bilgi amacli: su anda her karede NPC/boss basina SysFont cagriliyor.
        self.assertIsNotNone(avg)


def _record_diag_start(game):
    _record_diag_start.pos = (game.player.tx, game.player.ty)


_record_diag_start.pos = None


def _record_diagonal(game):
    """Capraz hareket denemesinin sonucunu kaydeder (rapor icin)."""
    _record_diagonal.result = (game.player.tx, game.player.ty, game.player.direction)


_record_diagonal.result = None


def _report(h_smoke, h_perf):
    tile = h_smoke.mod.TILE if hasattr(h_smoke, "mod") else 32
    # Olcumler yalnizca isaretli yuruyus penceresinden alinir: senaryonun
    # isinlamalari ve menude gecen kareler istatistigi bozmasin.
    a0 = h_smoke.marks.get("yuru_basla", 0)
    b0 = h_smoke.marks.get("yuru_bitti", 10 ** 9)
    trace = [p for p in h_smoke.pos_trace if a0 <= p[0] <= b0]
    steps, cam_steps = [], []
    for a, b in zip(trace, trace[1:]):
        d = abs(b[1] - a[1]) + abs(b[2] - a[2])
        if d:
            steps.append(round(d, 2))
        dc = abs(b[3] - a[3]) + abs(b[4] - a[4])
        if dc:
            cam_steps.append(dc)
    print("\n" + "=" * 62)
    print("  OLCUM RAPORU")
    print("=" * 62)
    ratio = len(steps) / max(1, len(trace) - 1)
    print(f"  Kare sayisi (surulen)      : {h_smoke.frames}")
    print(f"  Ekran goruntusu            : {len(h_smoke.shots)} adet -> {SHOT_DIR}")
    print(f"  --- yuruyus penceresi ({len(trace)} kare) ---")
    print(f"  Oyuncu adimi  en buyuk     : {max(steps):.1f} px (tile={tile})")
    print(f"  Oyuncu adimi  cesitleri    : {sorted(set(steps))} px")
    print(f"  Hareketli kare orani       : {len(steps)}/{len(trace)-1}  (%{ratio*100:.0f})")
    print(f"  Kamera adimi  en buyuk     : {max(cam_steps) if cam_steps else 0} px")
    print(f"  Capraz: {_record_diag_start.pos} -> {_record_diagonal.result}")
    if h_perf:
        times = h_perf.frame_times[-200:]
        calls = h_perf.sysfont_calls[-200:]
        avg = sum(times) / len(times)
        print(f"  Ham kare maliyeti (koy)    : {avg:.2f} ms  (~{1000/avg:.0f} FPS tavan)")
        print(f"  Kare basina SysFont()      : {sum(calls)/len(calls):.1f} cagri")
    print("=" * 62)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromModule(__import__("__main__"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _report(TestGameplaySmoke.h, getattr(TestPerformanceProbe, "h", None))
    raise SystemExit(0 if result.wasSuccessful() else 1)
