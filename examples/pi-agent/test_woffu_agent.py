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
        self.assertIn("6h fichadas y el horario pide 8h", msg)
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
