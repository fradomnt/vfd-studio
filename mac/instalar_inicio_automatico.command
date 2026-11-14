#!/bin/bash
# Faz o VFD Studio abrir sozinho sempre que o Mac ligar (e reabrir se fechar).
# Cria um LaunchAgent do usuário: ~/Library/LaunchAgents/studio.tekne.vfdstudio.plist
# Para desfazer: remover_inicio_automatico.command
cd "$(dirname "$0")/.." || exit 1
PASTA="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/studio.tekne.vfdstudio.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$PASTA/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>studio.tekne.vfdstudio</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$PASTA/iniciar.command</string><string>--sem-pausa</string>
  </array>
  <key>WorkingDirectory</key><string>$PASTA</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$PASTA/logs/vfdstudio.log</string>
  <key>StandardErrorPath</key><string>$PASTA/logs/vfdstudio.err.log</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/Library/Frameworks/Python.framework/Versions/Current/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>VFD_SEM_NAVEGADOR</key><string>1</string>
  </dict>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)/studio.tekne.vfdstudio" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && launchctl kickstart -k "gui/$(id -u)/studio.tekne.vfdstudio"
echo
echo "Pronto. O VFD Studio agora abre sozinho ao ligar o Mac e reabre se fechar."
echo "Página: http://127.0.0.1:8765   Logs: $PASTA/logs/"
echo
echo "FALTA UM PASSO MANUAL, só uma vez: Ajustes do Sistema > Usuários e Grupos > Login automático"
echo "para este usuário. Sem isso, depois de uma queda de luz o Mac para na tela de senha."
read -r -p "Enter para fechar..." _
