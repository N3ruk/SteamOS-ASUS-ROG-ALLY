#!/usr/bin/env python3
"""Run from extracted folder. Installation never requires running this script as root."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from installer import engine

ROOT = Path(__file__).resolve().parent
TITLE = 'SteamOS ASUS ROG ALLY — Instalador 1.0.0'


def message(text, error=False):
    print(text, flush=True)
    if shutil.which('kdialog') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        subprocess.run(['kdialog', '--title', TITLE, '--error' if error else '--msgbox', text])


def select(ids, failures):
    eligible = [i for i in ids if not failures[i]]
    overview = ('Marca lo que quieras instalar; todo empieza desmarcado.\n'
                'Instalar no cambia el arranque, TDP, SMT ni dispositivos Bluetooth.\n'
                'Los instaladores originales pueden pedir su propia confirmación o autorización.\n')
    unavailable = [engine.CATALOG[i]['name'] + ': ' + '; '.join(failures[i]) for i in ids if failures[i]]
    if unavailable:
        overview += '\nNo disponibles en este equipo:\n' + '\n'.join(unavailable)
    if not eligible:
        message(overview, error=True)
        return []
    if shutil.which('kdialog') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        command = ['kdialog', '--title', TITLE, '--geometry', '1100x650', '--separate-output', '--checklist', overview]
        for i in eligible:
            item = engine.CATALOG[i]
            command += [i, item['name'] + ' ' + item['version'] + ' — ' + item['description'], 'off']
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            return []
        chosen = [s.strip('"') for s in result.stdout.splitlines()]
    else:
        print(overview)
        for i in eligible:
            print(i + ': ' + engine.CATALOG[i]['name'] + '\n  ' + engine.CATALOG[i]['description'])
        chosen = input('IDs a instalar, separados por comas (vacío cancela): ').replace(' ', '').split(',')
        chosen = [s for s in chosen if s]
    if any(i not in eligible for i in chosen) or len(set(chosen)) != len(chosen):
        raise RuntimeError('Selección desconocida o repetida.')
    return chosen


def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument('--check', action='store_true', help='Comprobar sin instalar ni cambiar ajustes')
    parser.add_argument('--verify', action='store_true', help='Verificar solo integridad del paquete')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--component', choices=engine.CATALOG, help='Preselección individual, mantiene confirmación')
    args = parser.parse_args()
    engine.verify(ROOT)
    ids = engine.available(ROOT)
    if args.component:
        if args.component not in ids:
            raise RuntimeError('Componente ausente en este ZIP.')
        ids = [args.component]
    if args.verify:
        print('Integridad SHA256 OK.')
        return 0
    if os.geteuid() == 0:
        raise RuntimeError('Ejecuta como tu usuario normal, sin sudo. Los componentes que lo necesiten pedirán autorización.')
    failures = {i: engine.requirements(i, ROOT) for i in ids}
    if args.check:
        report = {i: {'name': engine.CATALOG[i]['name'], 'eligible': not failures[i], 'errors': failures[i]} for i in ids}
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else '\n'.join(
            engine.CATALOG[i]['name'] + ': ' + ('DISPONIBLE' if not failures[i] else '; '.join(failures[i])) for i in ids))
        return 0 if any(not failures[i] for i in ids) else 1
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        try:
            import gi
            gi.require_version('Gtk', '4.0')
            from gi.repository import Gtk
        except (ImportError, ValueError):
            pass  # SteamOS without GTK4 still has the native KDE checklist.
        else:
            from installer.ui import run
            return run(ROOT, ids, failures)
    chosen = select(ids, failures)
    if not chosen:
        return 0
    results, errors = [], False
    for component in chosen:
        print('Instalando: ' + engine.CATALOG[component]['name'], flush=True)
        try:
            info = engine.install(component, ROOT)
            results.append(engine.CATALOG[component]['name'] + ': ' + info)
        except Exception as exc:
            results.append(engine.CATALOG[component]['name'] + ': ERROR — ' + str(exc))
            errors = True
    message('\n\n'.join(results), errors)
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        if '--check' in sys.argv or '--verify' in sys.argv:
            print('ERROR: ' + str(exc), file=sys.stderr)
        else:
            message(str(exc), True)
        sys.exit(1)
