"""Unit tests for the pure helpers of woffu_agent.py (no network).

    python3 -m unittest examples/pi-agent/test_woffu_agent.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import woffu_agent as w  # noqa: E402


def sign(t, sid=1):
    return {"signId": sid, "time": t}


def slot(i, o, sid=1):
    return {"in": sign(i, sid), "out": sign(o, sid), "motive": None}


def wd(start="08:00:00", working=28800, *slots):
    return {
        "diarySummaryWorkday": {
            "startTime": start, "endTime1": "14:00:00", "startTime2": "15:00:00",
            "endTime": "17:00:00", "workingTime": working,
        },
        "signSlots": list(slots),
    }


class Horario(unittest.TestCase):
    def test_un_bloque_de_8h_lunes_a_jueves(self):
        self.assertEqual(w.tramos_horario(wd()), [("08:00:00", "16:00:00")])

    def test_un_bloque_de_6h_viernes(self):
        self.assertEqual(w.tramos_horario(wd("09:00:00", 21600)), [("09:00:00", "15:00:00")])

    def test_sin_horario(self):
        self.assertEqual(w.tramos_horario({"diarySummaryWorkday": {"workingTime": 0}}), [])
        self.assertEqual(w.tramos_horario(None), [])

    def test_horas_objetivo(self):
        self.assertEqual(w.horas_objetivo(wd()), 8.0)
        self.assertEqual(w.horas_objetivo(wd("09:00:00", 21600)), 6.0)


class ScheduleJson(unittest.TestCase):
    SCHED = {"mon": ("08:00:00", "16:00:00"), "fri": ("09:00:00", "15:00:00")}

    def test_fichero_de_ejemplo_carga_y_valida(self):
        s = w.load_schedule(os.path.join(os.path.dirname(__file__), "schedule.json"))
        self.assertEqual(s["mon"], ("08:00:00", "16:00:00"))
        self.assertEqual(s["fri"], ("09:00:00", "15:00:00"))
        self.assertNotIn("sat", s)

    def test_sin_fichero_devuelve_vacio(self):
        self.assertEqual(w.load_schedule("/nonexistent/schedule.json"), {})

    def test_json_manda_sobre_woffu(self):
        # 2026-09-21 is a Monday; Woffu says 07:00 + 7h, the file says 08:00-16:00.
        self.assertEqual(w.tramos_horario(wd("07:00:00", 25200), "2026-09-21", self.SCHED),
                         [("08:00:00", "16:00:00")])
        self.assertEqual(w.horas_objetivo(wd("07:00:00", 25200), "2026-09-21", self.SCHED), 8.0)

    def test_dia_ausente_en_json_usa_woffu(self):
        # 2026-09-22 is a Tuesday, not in SCHED.
        self.assertEqual(w.tramos_horario(wd("07:00:00", 25200), "2026-09-22", self.SCHED),
                         [("07:00:00", "14:00:00")])

    def test_validacion(self):
        import json, tempfile
        def load(days):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump({"days": days}, f)
            return w.load_schedule(f.name)
        with self.assertRaises(ValueError):
            load({"lunes": {"start": "08:00", "hours": 8}})
        with self.assertRaises(ValueError):
            load({"mon": {"start": "08:00"}})
        with self.assertRaises(ValueError):
            load({"mon": {"start": "20:00", "hours": 8}})
        self.assertEqual(load({"mon": None}), {})


class Firmas(unittest.TestCase):
    def test_plantillas_sin_signId_no_son_firmas(self):
        d = wd("08:00:00", 28800, slot("08:00:00", "14:00:00", 0), slot("15:00:00", "17:00:00", 0))
        self.assertEqual(w.firmas_persistidas(d), 0)
        self.assertEqual(w.horas_fichadas(d), (0.0, []))
        self.assertEqual(w.slots_completos(d), [])

    def test_entrada_abierta_cuenta_una_firma_y_cero_horas(self):
        d = wd("08:00:00", 28800, {"in": sign("08:03:00", 7), "out": sign("17:00:00", 0)})
        self.assertEqual(w.firmas_persistidas(d), 1)
        self.assertEqual(w.horas_fichadas(d)[0], 0.0)

    def test_bloque_unico_mas_sobrantes_colapsados(self):
        d = wd("08:00:00", 28800, slot("08:00:00", "16:00:00", 1),
               slot("16:00:00", "16:00:00", 2), slot("16:00:00", "16:00:00", 3))
        horas, franjas = w.horas_fichadas(d)
        self.assertEqual(horas, 8.0)
        self.assertEqual(franjas, ["08:00-16:00", "16:00-16:00", "16:00-16:00"])
        self.assertEqual(w.firmas_persistidas(d), 6)


class SegundosDeFichajeEnVivo(unittest.TestCase):
    """Regression: live signs carry seconds. 08:00:24-16:00:23 is 7h59m59s,
    not 8h; rounding to minutes let the day pass as complete (2026-09-24)."""

    DIA = wd("08:00:00", 28800, slot("08:00:24", "16:00:23", 1))

    def test_segundos_fichados_no_redondea(self):
        self.assertEqual(w.segundos_fichados(self.DIA), 28799)
        self.assertEqual(w._hms(28799), "7h59m59s")
        self.assertLess(w.horas_fichadas(self.DIA)[0], 8.0)

    def test_layout_con_segundos_no_coincide_con_el_objetivo(self):
        self.assertEqual(w.layout_persistido(self.DIA), [("08:00:24", "16:00:23")])
        self.assertNotEqual(w.layout_persistido(self.DIA), w.layout_objetivo(self.DIA))


class RedondeoA5Minutos(unittest.TestCase):
    """El fill sube cada extremo fichado al multiplo de 5 minutos superior,
    en vez de exigir el segundo exacto (modelo elegido 2026-10-01)."""

    def test_ceil5_sube_al_multiplo_superior(self):
        self.assertEqual(w._ceil5("08:00:24"), "08:05:00")
        self.assertEqual(w._ceil5("08:02:24"), "08:05:00")
        self.assertEqual(w._ceil5("08:04:59"), "08:05:00")
        self.assertEqual(w._ceil5("16:01:10"), "16:05:00")
        self.assertEqual(w._ceil5("15:58:00"), "16:00:00")

    def test_ceil5_no_mueve_una_hora_ya_en_la_franja(self):
        for t in ("08:00:00", "08:05:00", "16:00:00", "09:00:00", "15:00:00"):
            self.assertEqual(w._ceil5(t), t)

    def test_ceil5_no_pasa_de_medianoche(self):
        self.assertEqual(w._ceil5("23:58:00"), "23:59:59")
        self.assertEqual(w._ceil5("23:55:00"), "23:55:00")

    def test_objetivo_redondea_ambos_extremos(self):
        d = wd("08:00:00", 28800, slot("08:02:24", "16:01:10", 1))
        self.assertEqual(w.layout_objetivo(d), [("08:05:00", "16:05:00")])

    def test_objetivo_respeta_la_jornada_real_no_el_horario(self):
        # 10:07-18:03 no se reescribe a 08:00-16:00: solo se liman los extremos.
        d = wd("08:00:00", 28800, slot("10:07:00", "18:03:00", 1))
        self.assertEqual(w.layout_objetivo(d), [("10:10:00", "18:05:00")])

    def test_objetivo_deja_intacto_un_tramo_que_colapsaria(self):
        # Entrada y salida en la misma franja: redondear lo dejaria a cero y
        # el PUT devuelve 500 en un dia con firmas en vivo. Se deja como esta.
        d = wd("08:00:00", 28800, slot("08:01:00", "08:03:00", 1))
        self.assertEqual(w.layout_objetivo(d), [("08:01:00", "08:03:00")])

    def test_dia_ya_redondeado_no_necesita_escritura(self):
        d = wd("08:00:00", 28800, slot("08:05:00", "16:05:00", 1))
        self.assertEqual(w.layout_persistido(d), w.layout_objetivo(d))

    def test_dia_ya_correcto_coincide(self):
        ok = wd("08:00:00", 28800, slot("08:00:00", "16:00:00", 1))
        self.assertEqual(w.layout_persistido(ok), w.layout_objetivo(ok))


class RetocarFirma(unittest.TestCase):
    """Regression: forcing signType 3 onto a live sign (signType 0) makes the
    PUT return 500 _DefaultDetailError (2026-09-22). Preserve the original."""

    def test_conserva_signType_de_fichaje_en_vivo(self):
        c = w._retocar({"signId": 9, "time": "08:00:24", "signType": 0}, "08:00:00")
        self.assertEqual(c["signType"], 0)
        self.assertEqual(c["time"], "08:00:00")
        self.assertEqual(c["signStatus"], 1)
        self.assertEqual(c["signId"], 9)

    def test_pone_3_si_la_firma_no_lo_trae(self):
        self.assertEqual(w._retocar({"signId": 9, "time": "x"}, "08:00:00")["signType"], 3)


class ReintentosDeRed(unittest.TestCase):
    """Regression: an uncaught gaierror killed the whole 22:00 pass (2026-09-22)."""

    def test_reintenta_y_devuelve_error_sin_lanzar(self):
        import urllib.error
        intentos = []
        orig_once, orig_sleep = w._req_once, w.time.sleep
        w._req_once = lambda *a, **k: (intentos.append(1),
                                       (_ for _ in ()).throw(urllib.error.URLError("dns")))[1]
        w.time.sleep = lambda s: None
        try:
            st, detalle = w._req({"WOFFU_BASE_URL": "x", "WOFFU_TOKEN": "y"}, "GET", "/p")
        finally:
            w._req_once, w.time.sleep = orig_once, orig_sleep
        self.assertEqual(len(intentos), w.REQ_INTENTOS)
        self.assertEqual(st, 0)
        self.assertIn("fallo de red", detalle)

    def test_no_reintenta_si_la_llamada_funciona(self):
        orig = w._req_once
        w._req_once = lambda *a, **k: (200, {"ok": True})
        try:
            self.assertEqual(w._req({}, "GET", "/p"), (200, {"ok": True}))
        finally:
            w._req_once = orig


class PuertaDeConfirmacion(unittest.TestCase):
    """confirmar_dia only reaches the confirm endpoint when signed == scheduled."""

    def _run(self, day_wd, accepted=None):
        calls = []
        orig_req, orig_pres, orig_wd = w._req, w.presence, w.workday
        w.presence = lambda env, day: {"accepted": accepted, "diarySummaryId": 42}
        w.workday = lambda env, day: day_wd
        w._req = lambda env, m, p, body=None: calls.append((m, p, body)) or (200, None)
        try:
            msg = w.confirmar_dia({"WOFFU_USER_ID": "1", "_schedule": {}}, "2026-09-21")
        finally:
            w._req, w.presence, w.workday = orig_req, orig_pres, orig_wd
        return msg, calls

    def test_cero_horas_no_confirma(self):
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:00:00", "14:00:00", 0)))
        self.assertIn("NO se confirma", msg)
        self.assertEqual(calls, [])

    def test_seis_horas_en_dia_de_ocho_no_confirma(self):
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:00:00", "14:00:00", 1)))
        self.assertIn("6h00m00s fichados y el horario pide 8h00m00s", msg)
        self.assertEqual(calls, [])

    def test_un_segundo_de_menos_si_confirma(self):
        # Modelo 2026-10-01: margen de 5 minutos. 7h59m59s cuadra.
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:00:24", "16:00:23", 1)))
        self.assertEqual(msg, "")
        self.assertEqual(len(calls), 1)

    def test_dentro_del_margen_de_5_minutos_confirma(self):
        # 08:05-16:01 = 7h56m, dentro de los 5 minutos de margen.
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:05:00", "16:01:00", 1)))
        self.assertEqual(msg, "")
        self.assertEqual(len(calls), 1)

    def test_mas_de_5_minutos_de_menos_no_confirma(self):
        # 08:05-15:59 = 7h54m, se pasa del margen.
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:05:00", "15:59:00", 1)))
        self.assertIn("7h54m00s fichados y el horario pide 8h00m00s", msg)
        self.assertEqual(calls, [])

    def test_margen_simetrico_por_exceso(self):
        # 08:00-16:04 = 8h04m, dentro del margen. 08:00-16:06 se pasa.
        self.assertEqual(self._run(wd("08:00:00", 28800, slot("08:00:00", "16:04:00", 1)))[0], "")
        self.assertIn("NO se confirma",
                      self._run(wd("08:00:00", 28800, slot("08:00:00", "16:06:00", 1)))[0])

    def test_nueve_horas_en_dia_de_ocho_no_confirma(self):
        # 2026-09-22: dos tramos manuales, 9h. Pasarse del margen no se confirma.
        d = wd("08:00:00", 28800, slot("08:00:24", "14:00:00", 1), slot("15:00:00", "18:00:00", 2))
        msg, calls = self._run(d)
        self.assertIn("fichados y el horario pide 8h00m00s", msg)
        self.assertEqual(calls, [])

    def test_ocho_horas_confirma(self):
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:00:00", "16:00:00", 1)))
        self.assertEqual(msg, "")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1].endswith("/diarysummaries/confirm"))
        self.assertEqual(calls[0][2], {"diarySummaryIds": [42]})

    def test_seis_horas_viernes_confirma(self):
        msg, calls = self._run(wd("09:00:00", 21600, slot("09:00:00", "15:00:00", 1)))
        self.assertEqual(msg, "")
        self.assertEqual(len(calls), 1)

    def test_ya_confirmado_no_hace_nada(self):
        msg, calls = self._run(wd("08:00:00", 28800, slot("08:00:00", "16:00:00", 1)), accepted=True)
        self.assertEqual((msg, calls), ("", []))


if __name__ == "__main__":
    unittest.main()
