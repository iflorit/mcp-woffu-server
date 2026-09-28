#!/usr/bin/env python3
"""Agente Woffu para Raspberry Pi: rellena la jornada al horario asignado.

  # ticks de fichaje en vivo cada media hora hasta la noche: cada tick decide
  # por si mismo si toca entrar o salir; un tick perdido se recupera en el
  # siguiente (la hora real da igual, el fill de las 22:00 la ajusta).
  0,30 8-21 * * 1-5  /usr/bin/python3 /home/pi/woffu/woffu_agent.py clock
  # cada dia laborable a las 22:00 CEST: deja hoy y los ultimos CATCHUP_DAYS
  # dias del mes en un UNICO bloque de las horas asignadas (8h L-J, 6h V
  # segun lo que diga Woffu para ese dia) y confirma solo si cuadran.
  0 22 * * 1-5   /usr/bin/python3 /home/pi/woffu/woffu_agent.py fill
  # informe semanal del lunes por la mañana
  0 8 * * 1      /usr/bin/python3 /home/pi/woffu/woffu_agent.py report

COMO SE ESCRIBEN LAS HORAS (aprendido capturando la propia web, 2026-09-07)

El endpoint `PUT /api/svc/core/users/{uid}/diarysummaries/workday/slots/self`
NO crea fichajes: EDITA los que ya existen. Enviar firmas con `signId: 0`
devuelve 200 y no persiste nada -- ese silencio costo varias iteraciones de
diagnostico. Lo que la web manda, y lo unico que funciona, es la firma
existente entera con su `signId` real, cambiando solo `time` y poniendo
`signStatus: 1` / `signType: 3`.

De ahi la consecuencia central: SIN FIRMAS PREVIAS NO SE PUEDE RELLENAR EL
DIA. El fill corrige las horas de un dia ya fichado; no inventa un dia
entero desde cero. Las firmas las crea el comando `clock` EN VIVO (POST
/api/svc/signs/signs siempre graba la hora actual, ignora cualquier fecha),
por eso hay un cron cada media hora: entrada al inicio del horario, salida
cuando se cumplen las horas asignadas. El fill de las 22:00 ajusta luego
esas firmas al bloque exacto. Un dia sin ninguna firma (Pi apagada) se
reporta por Slack para arreglarlo a mano en la web.

OBJETIVO: un unico bloque por dia, de inicio del horario a inicio + horas
asignadas (08:00-16:00 L-J, 09:00-15:00 V). Solo se confirma un dia cuyas
firmas persistidas suman exactamente las horas asignadas.

Y un slot sobrante no se puede borrar: ni `deleted: True` ni omitirlo del
payload surten efecto (200 y sigue ahi). Se colapsa a duracion cero
solapandolo con el final del ultimo tramo, que es inocuo para el computo.

Config en .env junto a este script:
  WOFFU_BASE_URL, WOFFU_TOKEN, WOFFU_USER_ID   (obligatorios)
  SLACK_BOT_TOKEN / SLACK_CHANNEL              (opcional, avisos)
  SLACK_WEBHOOK_URL                            (opcional, alternativa)

Bloque objetivo por dia de la semana en schedule.json (opcional):
  {"days": {"mon": {"start": "08:00", "hours": 8}, ..., "fri": {"start": "09:00", "hours": 6}}}
Los dias ausentes o null usan el horario que Woffu asigne ese dia (inicio +
horas asignadas). Fines de semana, festivos y ausencias se saltan siempre.
"""

import json
import logging
import smtplib
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "woffu_agent.log"

log = logging.getLogger("woffu")


def setup_logging():
    """Called from main(), never at import: importing the module (tests)
    must not create files."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )

SCHEDULE_FILE = BASE_DIR / "schedule.json"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Dias hacia atras que repasa cada pase. Nunca cruza al mes anterior: los
# periodos cerrados descartan escrituras en silencio.
CATCHUP_DAYS = 30


def load_env() -> dict:
    env = {}
    f = BASE_DIR / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    falta = [k for k in ("WOFFU_BASE_URL", "WOFFU_TOKEN", "WOFFU_USER_ID") if not env.get(k)]
    if falta:
        sys.exit("Falta configuracion en .env: " + ", ".join(falta))
    return env


REQ_INTENTOS = 3


def _req(env: dict, method: str, path: str, body=None):
    """Reintenta los fallos de RED (DNS caido, timeout, conexion cortada).
    Un `gaierror` sin capturar mataba el pase de las 22:00 entero: el dia se
    quedaba sin rellenar y sin aviso."""
    ultimo = None
    for intento in range(REQ_INTENTOS):
        try:
            return _req_once(env, method, path, body)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            ultimo = e
            if intento < REQ_INTENTOS - 1:
                espera = 5 * (intento + 1)
                log.warning("red: %s %s fallo (%s), reintento en %ds", method, path, e, espera)
                time.sleep(espera)
    log.error("red: %s %s agoto %d intentos: %s", method, path, REQ_INTENTOS, ultimo)
    return 0, "fallo de red: %s" % ultimo


def _req_once(env: dict, method: str, path: str, body=None):
    url = env["WOFFU_BASE_URL"] + path
    headers = {
        "Authorization": "Bearer " + env["WOFFU_TOKEN"],
        "Accept": "application/json, text/plain, */*",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        detalle = ""
        try:
            detalle = e.read().decode()[:200]
        except Exception:
            pass
        return e.code, detalle


def notify(env: dict, title: str, message: str):
    enviado = False
    if env.get("SLACK_BOT_TOKEN") and env.get("SLACK_CHANNEL"):
        try:
            req = urllib.request.Request(
                "https://slack.com/api/chat.postMessage",
                data=json.dumps({"channel": env["SLACK_CHANNEL"],
                                 "text": "*%s*\n%s" % (title, message)}).encode(),
                headers={"Content-Type": "application/json; charset=utf-8",
                         "Authorization": "Bearer " + env["SLACK_BOT_TOKEN"]},
                method="POST")
            resp = json.load(urllib.request.urlopen(req, timeout=30))
            if resp.get("ok"):
                log.info("Slack: mensaje enviado a %s", env["SLACK_CHANNEL"])
                enviado = True
            else:
                log.error("Slack error: %s", resp.get("error"))
        except Exception as e:
            log.error("Slack fallo: %s", e)
    if not enviado and env.get("SLACK_WEBHOOK_URL"):
        try:
            req = urllib.request.Request(
                env["SLACK_WEBHOOK_URL"],
                data=json.dumps({"text": "*%s*\n%s" % (title, message)}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=30)
            log.info("Slack: webhook enviado")
            enviado = True
        except Exception as e:
            log.error("Webhook fallo: %s", e)
    if not enviado:
        log.warning("Sin canal de aviso disponible; solo queda en el log")


def _hhmm(t: str) -> int:
    """Minutos desde medianoche (para horarios, que siempre son :00)."""
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def _segundos(t: str) -> int:
    """Segundos desde medianoche. Woffu cuenta los segundos: una firma en
    vivo a las 08:00:24 con salida a las 16:00:23 son 7h59m59s, no 8h, y
    redondear a minutos hacia hacia hacia daba el dia por bueno."""
    partes = (t.split(":") + ["0", "0"])[:3]
    return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])


def workday(env: dict, day: str):
    """Horario asignado + firmas reales del dia, en una sola llamada."""
    st, data = _req(env, "GET",
                    "/api/svc/core/users/%s/diarysummaries/workday/slots?date=%s"
                    % (env["WOFFU_USER_ID"], day))
    return data if st == 200 else None


def presence(env: dict, day: str):
    uid = env["WOFFU_USER_ID"]
    st, data = _req(env, "GET",
                    "/api/svc/core/diariesquery/users/%s/diaries/summary/presence"
                    "?userId=%s&fromDate=%s&toDate=%s&pageSize=1&includeDifference=true"
                    % (uid, uid, day, day))
    diarios = (data or {}).get("diaries") or []
    return diarios[0] if diarios else None


def dia_no_laborable(diary) -> str:
    """Motivo por el que el dia no se debe rellenar, o cadena vacia."""
    if not diary:
        return "sin diario"
    if diary.get("isWeekend"):
        return "fin de semana"
    if diary.get("isHoliday"):
        return "festivo"
    if diary.get("isEvent"):
        return "evento"
    if diary.get("absenceEvents") or diary.get("pendingAbsenceEvents"):
        return "ausencia/vacaciones"
    return ""


def _hms(segundos: int) -> str:
    return "%dh%02dm%02ds" % (segundos // 3600, segundos % 3600 // 60, segundos % 60)


def _seg_hhmmss(seg: int) -> str:
    return "%02d:%02d:%02d" % (seg // 3600, seg % 3600 // 60, seg % 60)


def _min_hhmm(m: int) -> str:
    return "%02d:%02d:00" % (m // 60, m % 60)


def load_schedule(path=SCHEDULE_FILE) -> dict:
    """Bloques objetivo por dia de la semana, validados. {} si no hay fichero."""
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text())
    out = {}
    for k, v in (data.get("days") or {}).items():
        if k not in WEEKDAYS:
            raise ValueError("schedule.json: dia desconocido %r" % k)
        if v is None:
            continue
        ini, horas = v.get("start"), v.get("hours")
        if not ini or horas is None or float(horas) <= 0:
            raise ValueError("schedule.json: %s necesita start y hours > 0" % k)
        fin_min = _hhmm(ini) + int(round(float(horas) * 60))
        if fin_min > 24 * 60:
            raise ValueError("schedule.json: %s termina pasada la medianoche" % k)
        out[k] = (ini[:5] + ":00", _min_hhmm(fin_min))
    return out


def tramos_horario(wd, day: str = None, schedule: dict = None) -> list:
    """Un unico tramo (inicio, fin) para el dia.

    Prioridad: schedule.json para ese dia de la semana; si no, el horario
    asignado por Woffu (inicio + `workingTime`). Asi un viernes de 6h, un
    cambio de turno o un festivo salen bien sin tocar el agente."""
    if day and schedule:
        clave = WEEKDAYS[date.fromisoformat(day).weekday()]
        if clave in schedule:
            return [schedule[clave]]
    s = (wd or {}).get("diarySummaryWorkday") or {}
    ini = (s.get("startTime") or "")[:8]
    segundos = int(s.get("workingTime") or 0)
    if not ini or segundos <= 0:
        return []
    return [(ini, _min_hhmm(_hhmm(ini) + segundos // 60))]


def horas_objetivo(wd, day: str = None, schedule: dict = None) -> float:
    return sum(_hhmm(f) - _hhmm(i) for i, f in tramos_horario(wd, day, schedule)) / 60.0


def firmas_persistidas(wd) -> int:
    """Numero de firmas reales (in u out con signId > 0)."""
    n = 0
    for sl in (wd or {}).get("signSlots") or []:
        for k in ("in", "out"):
            if ((sl.get(k) or {}).get("signId") or 0) > 0:
                n += 1
    return n


def slots_completos(wd) -> list:
    """Solo los pares in/out ya persistidos: son los unicos editables."""
    out = []
    for sl in (wd or {}).get("signSlots") or []:
        i, o = sl.get("in") or {}, sl.get("out") or {}
        if (i.get("signId") or 0) > 0 and (o.get("signId") or 0) > 0:
            out.append(sl)
    return out


def segundos_fichados(wd) -> int:
    """Segundos realmente fichados, con precision de segundo."""
    return sum(_segundos(sl["out"]["time"]) - _segundos(sl["in"]["time"])
               for sl in slots_completos(wd))


def horas_fichadas(wd) -> tuple:
    franjas = ["%s-%s" % (sl["in"]["time"][:5], sl["out"]["time"][:5])
               for sl in slots_completos(wd)]
    return segundos_fichados(wd) / 3600.0, franjas


def layout_persistido(wd) -> list:
    """Pares (entrada, salida) tal cual estan persistidos, con segundos."""
    return [(sl["in"]["time"], sl["out"]["time"]) for sl in slots_completos(wd)]


def layout_objetivo(tramos: list, n_slots: int) -> list:
    """Como debe quedar el dia con las `n_slots` firmas que ya existen.

    Con un solo slot, el bloque tal cual. Con mas slots que tramos hay que
    REPARTIR el bloque en tramos contiguos (08:00-12:00, 12:00-16:00) en vez
    de colapsar los sobrantes a duracion cero: el PUT devuelve 500
    `_DefaultDetailError` si se le manda un tramo de longitud cero en un dia
    cuya primera firma es un fichaje en vivo (`signType` 0). Contiguos suman
    lo mismo y Woffu los acepta."""
    sobrantes = max(0, n_slots - len(tramos))
    if not sobrantes:
        return [(i, f) for i, f in tramos]
    ini, fin = tramos[0][0], tramos[-1][1]
    total = _segundos(fin) - _segundos(ini)
    trozos = len(tramos) + sobrantes
    cortes = [_segundos(ini) + total * k // trozos for k in range(trozos + 1)]
    return [(_seg_hhmmss(cortes[k]), _seg_hhmmss(cortes[k + 1])) for k in range(trozos)]


def _retocar(firma: dict, nueva_hora: str) -> dict:
    """La firma existente, entera, con la hora cambiada.

    Conservar `signId` y el resto de campos es lo que hace que el PUT
    persista: es una edicion, no un alta. Y hay que conservar tambien el
    `signType` ORIGINAL: forzarlo a 3 (edicion web) sobre una firma creada
    en vivo (`signType` 0) hace que el PUT devuelva 500
    `_DefaultDetailError`; el dia se quedaba sin corregir para siempre."""
    c = dict(firma)
    c["time"] = nueva_hora
    c["signStatus"] = 1
    c.setdefault("signType", 3)
    return c


def rellenar_dia(env: dict, day: str) -> tuple:
    """Deja la jornada exactamente en su horario. (ok, mensaje)."""
    diary = presence(env, day)
    motivo = dia_no_laborable(diary)
    if motivo:
        return True, ""
    if diary.get("accepted") is True:
        return True, ""  # confirmado y bloqueado: no hay nada que editar

    wd = workday(env, day)
    tramos = tramos_horario(wd, day, env.get("_schedule"))
    if not tramos:
        return True, ""

    esperadas = sum(_hhmm(f) - _hhmm(i) for i, f in tramos) / 60.0
    actuales, franjas = horas_fichadas(wd)
    # Woffu rechaza (400 _SignAddError) firmas con hora futura: hoy solo se
    # puede rellenar una vez pasado el fin del bloque.
    ahora = datetime.now()
    if day == ahora.date().isoformat() and ahora.hour * 60 + ahora.minute < _hhmm(tramos[-1][1]):
        return False, ("%s: todavia no son las %s, se rellenara en el pase de las 22:00"
                       % (day, tramos[-1][1][:5]))

    existentes = slots_completos(wd)
    # "Ya esta bien" se decide comparando el LAYOUT exacto (con segundos), no
    # las horas: 08:00:24-16:00:23 suma 8h al redondear a minutos y el dia se
    # quedaba con 7h59 sin que nadie lo tocase.
    if layout_persistido(wd) == layout_objetivo(tramos, len(existentes)):
        return True, ""

    if len(existentes) < len(tramos):
        return False, ("%s: %g/%gh -- solo %d franja(s) fichada(s) y el horario "
                       "necesita %d. La API solo puede EDITAR fichajes que ya "
                       "existan, asi que este dia hay que completarlo a mano "
                       "en la web." % (day, actuales, esperadas, len(existentes), len(tramos)))

    ms = int(time.time() * 1000)
    objetivo = layout_objetivo(tramos, len(existentes))
    slots = []
    for idx, sl in enumerate(existentes):
        ini, fin = objetivo[idx]
        slots.append({"id": "%d-%d" % (ms, idx),
                      "in": _retocar(sl["in"], ini),
                      "out": _retocar(sl["out"], fin),
                      "motive": None,
                      "totalMin": (_segundos(fin) - _segundos(ini)) // 60})

    st, detalle = _req(env, "PUT",
                       "/api/svc/core/users/%s/diarysummaries/workday/slots/self" % env["WOFFU_USER_ID"],
                       {"date": day, "comments": "", "userId": int(env["WOFFU_USER_ID"]),
                        "slots": slots})
    if st != 200:
        return False, "%s: el PUT devolvio %s %s" % (day, st, detalle)

    time.sleep(6)
    wd2 = workday(env, day)
    nuevas, franjas2 = horas_fichadas(wd2)
    objetivo_s = sum(_segundos(f) - _segundos(i) for i, f in tramos)
    if segundos_fichados(wd2) != objetivo_s:
        return False, ("%s: tras rellenar quedan %s en vez de %s (%s)"
                       % (day, _hms(segundos_fichados(wd2)), _hms(objetivo_s),
                          " ".join(franjas2)))
    log.info("fill %s: %g -> %gh  %s", day, actuales, nuevas, " ".join(franjas2))
    return True, ""


def confirmar_dia(env: dict, day: str) -> str:
    """Confirma la jornada. Devuelve mensaje de error o cadena vacia."""
    diary = presence(env, day)
    if not diary:
        return ""
    if diary.get("accepted") is True:
        return ""
    # Regla dura, independiente del fill: solo se confirma si las firmas
    # persistidas cubren exactamente las horas asignadas.
    wd = workday(env, day)
    tramos = tramos_horario(wd, day, (env or {}).get("_schedule"))
    # Igualdad EXACTA en segundos, sin tolerancia: el fill siempre escribe
    # horas en punto, asi que lo exacto es alcanzable, y una tolerancia de
    # medio minuto dejaba pasar los 7h59m59s de un fichaje en vivo.
    objetivo_s = sum(_segundos(f) - _segundos(i) for i, f in tramos)
    fichados_s = segundos_fichados(wd)
    if objetivo_s <= 0 or fichados_s != objetivo_s:
        _, franjas = horas_fichadas(wd)
        return ("%s: NO se confirma, %s fichados y el horario pide %s (%s)"
                % (day, _hms(fichados_s), _hms(objetivo_s),
                   " ".join(franjas) or "sin fichajes"))
    uid = int(env["WOFFU_USER_ID"])
    # accepted=False significa "invalidada" (editada tras confirmarse) y el
    # endpoint de confirmar la ignora en silencio: primero hay que devolverla
    # a pendiente.
    if diary.get("accepted") is False:
        _req(env, "PUT", "/api/svc/core/users/diarysummaries/accept",
             {"acceptDiarySummaries": [{"userId": uid, "date": day, "accepted": True}]})
        time.sleep(3)
        diary = presence(env, day) or {}
    dsid = diary.get("diarySummaryId")
    if not dsid:
        return "%s: sin diarySummaryId, no se puede confirmar" % day
    st, detalle = _req(env, "PUT",
                       "/api/svc/core/diariesquery/users/diarysummaries/confirm",
                       {"diarySummaryIds": [dsid]})
    if st != 200:
        return "%s: confirmar devolvio %s %s" % (day, st, detalle)
    return ""


def resumen_semana(env: dict, hasta: date) -> tuple:
    dias = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
    lineas, total = [], 0.0
    d = hasta - timedelta(days=hasta.weekday())
    while d <= hasta:
        day = d.isoformat()
        diary = presence(env, day)
        motivo = dia_no_laborable(diary)
        etiqueta = "%s %s" % (dias[d.weekday()], d.strftime("%d/%m"))
        if motivo:
            if d.weekday() < 5:
                lineas.append("%-10s --    %s" % (etiqueta, motivo))
        else:
            h, franjas = horas_fichadas(workday(env, day))
            total += h
            lineas.append("%-10s %-5s %s" % (etiqueta, "%gh" % h,
                                             " ".join(franjas) or "sin fichajes"))
        d += timedelta(days=1)
    lineas.append("-" * 34)
    lineas.append("%-10s %gh" % ("Total", total))
    return lineas, total


def cmd_fill(env: dict, explicito) -> int:
    hoy = date.today()
    if explicito:
        objetivo = [explicito]
    else:
        primero = max(hoy - timedelta(days=CATCHUP_DAYS - 1), hoy.replace(day=1))
        objetivo = []
        d = primero
        while d <= hoy:
            objetivo.append(d.isoformat())
            d += timedelta(days=1)

    problemas = []
    for day in objetivo:
        # Un dia que falla no puede tumbar el pase entero (ni el aviso final).
        try:
            ok, msg = rellenar_dia(env, day)
            if not ok:
                problemas.append(msg)
                continue
            err = confirmar_dia(env, day)
            if err:
                problemas.append(err)
        except Exception as e:
            log.exception("fill %s fallo", day)
            problemas.append("%s: %s" % (day, e))
    # Resumen de la semana en curso, para el aviso de Slack.
    try:
        lineas, total = resumen_semana(env, hoy)
    except Exception as e:
        log.exception("resumen semanal fallo")
        lineas, total = ["(resumen no disponible: %s)" % e], 0.0
    cuerpo = "\n".join(lineas)
    if problemas:
        cuerpo += "\n\nATENCION:\n" + "\n".join(problemas)
    notify(env, "Woffu: jornadas al dia (%s)" % hoy.strftime("%d/%m"),
           "```%s```" % cuerpo)
    log.info("fill: %d problemas", len(problemas))
    return 0 if not problemas else 1

def cmd_clock(env: dict) -> int:
    """Tick de cron: crea las firmas del dia EN VIVO. Solo importa que existan
    una entrada y una salida antes del fill de las 22:00 (que las ajusta al
    bloque exacto), no la hora en que se graban. Dos reglas, decididas por
    la PARIDAD de las firmas persistidas, asi que repetir el tick nunca ficha
    dos veces y un tick perdido se recupera en el siguiente:
      - sin firmas y ya paso el inicio del bloque -> entrada
      - jornada abierta (firmas impares) y ya paso el fin -> salida"""
    hoy = date.today()
    ahora = datetime.now()
    day = hoy.isoformat()
    motivo = dia_no_laborable(presence(env, day))
    if motivo:
        log.info("clock: hoy no es laborable (%s)", motivo)
        return 0
    wd = workday(env, day)
    tramos = tramos_horario(wd, day, env.get("_schedule"))
    if not tramos:
        log.warning("clock: sin horario asignado hoy")
        return 0
    inicio, fin = tramos[0]
    n = firmas_persistidas(wd)
    ahora_min = ahora.hour * 60 + ahora.minute

    def fichar(entrada: bool, etiqueta: str) -> int:
        st, resp = _req(env, "POST", "/api/svc/signs/signs",
                        {"UserId": int(env["WOFFU_USER_ID"]), "signIn": entrada})
        if st not in (200, 201):
            notify(env, "Woffu ERROR", "fichaje %s (%s) fallo: HTTP %s %s"
                   % ("entrada" if entrada else "salida", etiqueta, st, resp))
            return 1
        log.info("clock: %s %s a las %s -> %s", "entrada" if entrada else "salida",
                 etiqueta, ahora.strftime("%H:%M"), resp)
        return 0

    if n == 0 and ahora_min >= _hhmm(inicio):
        return fichar(True, inicio[:5])
    if n % 2 == 1 and ahora_min >= _hhmm(fin):
        rc = fichar(False, fin[:5])
        if rc == 0:
            lineas, _ = resumen_semana(env, hoy)
            notify(env, "Woffu: jornada fichada (%s)" % hoy.strftime("%d/%m"),
                   "```%s```" % "\n".join(lineas))
        return rc
    log.info("clock: %s nada que hacer (%d firmas, bloque %s-%s)",
             ahora.strftime("%H:%M"), n, inicio[:5], fin[:5])
    return 0


def cmd_report(env: dict) -> int:
    hoy = date.today()
    lunes_pasado = hoy - timedelta(days=hoy.weekday() + 7)
    viernes = lunes_pasado + timedelta(days=4)
    lineas, total = resumen_semana(env, viernes)
    cuerpo = "\n".join(lineas)
    notify(env, "Woffu: semana %s a %s" % (lunes_pasado.strftime("%d/%m"),
                                           viernes.strftime("%d/%m")),
           "```%s```" % cuerpo)
    log.info("report:\n%s", cuerpo)
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("fill", "report", "clock"):
        sys.exit("Uso: woffu_agent.py clock | fill [YYYY-MM-DD] | report")
    setup_logging()
    env = load_env()
    env["_schedule"] = load_schedule()
    if env["_schedule"]:
        log.info("schedule.json: %s", {k: "%s-%s" % (i[:5], f[:5]) for k, (i, f) in env["_schedule"].items()})
    if args[0] == "fill":
        sys.exit(cmd_fill(env, args[1] if len(args) > 1 else None))
    if args[0] == "clock":
        sys.exit(cmd_clock(env))
    sys.exit(cmd_report(env))


if __name__ == "__main__":
    main()
