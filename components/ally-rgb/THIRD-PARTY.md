# Referencias y avisos

- Template y API de Decky: https://github.com/SteamDeckHomebrew/decky-plugin-template
  y https://github.com/SteamDeckHomebrew/loader-api. Se usan las dependencias oficiales
  @decky/api, @decky/ui y @decky/rollup. Los textos de licencia presentes en las dependencias
  se conservan en licenses/; React/UI se proporcionan por Decky en ejecución.
- Ally Center, de Keith Baker / Pixel Addict Games (MIT):
  https://github.com/PixelAddictUnlocked/allycenter/blob/main/main.py
  Referencia del ABI de cuatro colores RRGGBB para la interfaz sysfs de la Ally.
  No se incluyen sus controles de potencia, carga, ventilación ni MCU.
- HueSync, de honjow (BSD-3-Clause): https://github.com/honjow/HueSync
  Referencia de investigación y capacidades. No se incluye código de su backend,
  ni sus submódulos pyserial/HID ni dependencias para otras marcas.
- ABI LED del kernel: https://docs.kernel.org/leds/leds-class-multicolor.html
- Transporte hidraw de Linux: https://www.kernel.org/doc/html/latest/hid/hidraw.html
  Implementación propia con biblioteca estándar, sin libhid/pyserial.
- Formato de informes RGB del driver hid-asus-ally, Luke D. Jones:
  https://github.com/uejji/hid-asus-ally/blob/master/hid-asus-ally.c
  y su cabecera. Se consultaron los comandos LED de color `5a d1 08 0c` y
  brillo `5a ba c5 c4`; no se incorpora el código C del controlador ni sus
  comandos de mando/calibración/firmware. El repositorio es una referencia
  histórica de protocolo, no un módulo que se instale ni una dependencia.

El nombre ASUS/ROG identifica compatibilidad; este plugin no es software oficial de ASUS o Valve.
