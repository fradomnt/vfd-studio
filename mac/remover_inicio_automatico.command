#!/bin/bash
# Desfaz o instalar_inicio_automatico.command.
PLIST="$HOME/Library/LaunchAgents/studio.tekne.vfdstudio.plist"
launchctl bootout "gui/$(id -u)/studio.tekne.vfdstudio" 2>/dev/null
rm -f "$PLIST"
echo "Início automático removido. O VFD Studio volta a abrir só pelo iniciar.command."
read -r -p "Enter para fechar..." _
