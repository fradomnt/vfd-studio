#!/bin/bash
# Gera o instalador do Mac: dist/VFD-Studio-<versão>-mac.pkg. Rodar NO MAC, na pasta do projeto.
# Quem recebe o .pkg: duplo clique > Continuar > Instalar. Ele coloca o app em
# /Applications/VFD Studio/VFD Studio.app, mantém cenas.json/config.json de uma instalação anterior,
# deixa a pasta gravável para o usuário e abre o app no fim.
# O .pkg sai sem assinatura da Apple (veja o README, "Instalar em outro Mac").
cd "$(dirname "$0")/.." || exit 1
pausar() { [ -t 0 ] && read -r -p "Enter para fechar..." _; }

VERSAO=$(sed -n 's/^VERSAO *= *"\(.*\)"/\1/p' caminhos.py)
[ -n "$VERSAO" ] || { echo "Versão não encontrada em caminhos.py"; pausar; exit 1; }
ID="br.com.frado.vfdstudio"

echo "== 1/3 Gerando o app..."
bash mac/gerar_app.command </dev/null >/dev/null 2>&1
[ -d "dist/VFD Studio.app" ] || { echo "Falhou ao gerar o app (rode mac/gerar_app.command para ver o erro)."; pausar; exit 1; }

echo "== 2/3 Montando o pacote..."
TMP=$(mktemp -d)
mkdir -p "$TMP/raiz/VFD Studio" "$TMP/scripts"
ditto "dist/VFD Studio.app" "$TMP/raiz/VFD Studio/VFD Studio.app"
cp README.md "$TMP/raiz/VFD Studio/LEIA-ME.md"

# antes de instalar: fecha o VFD Studio se estiver aberto (ele apaga a tela ao sair)
cat > "$TMP/scripts/preinstall" <<'EOF'
#!/bin/bash
pkill -TERM -f "VFD Studio.app/Contents/MacOS/VFD Studio" 2>/dev/null && sleep 2
exit 0
EOF

# depois de instalar: pasta do usuário (o app grava cenas.json/config.json/logs ao lado dele) e abre o app
cat > "$TMP/scripts/postinstall" <<'EOF'
#!/bin/bash
PASTA="/Applications/VFD Studio"
USUARIO=$(stat -f%Su /dev/console)
if [ -n "$USUARIO" ] && [ "$USUARIO" != "root" ]; then
  chown -R "$USUARIO":staff "$PASTA"
  xattr -cr "$PASTA/VFD Studio.app" 2>/dev/null
  UID_U=$(id -u "$USUARIO")
  launchctl asuser "$UID_U" sudo -u "$USUARIO" open "$PASTA/VFD Studio.app" 2>/dev/null &
fi
exit 0
EOF
chmod +x "$TMP/scripts/preinstall" "$TMP/scripts/postinstall"

# o app não pode ser "realocado" para outra cópia achada no disco: instala sempre em Aplicativos
pkgbuild --analyze --root "$TMP/raiz" "$TMP/componentes.plist" >/dev/null
plutil -replace 0.BundleIsRelocatable -bool NO "$TMP/componentes.plist"

pkgbuild --quiet --root "$TMP/raiz" --component-plist "$TMP/componentes.plist" \
  --scripts "$TMP/scripts" --identifier "$ID" --version "$VERSAO" \
  --install-location /Applications "$TMP/vfdstudio.pkg" || { echo "pkgbuild falhou"; pausar; exit 1; }

echo "== 3/3 Gerando o instalador..."
SAIDA="dist/VFD-Studio-$VERSAO-mac.pkg"
productbuild --quiet --identifier "$ID" --version "$VERSAO" \
  --package "$TMP/vfdstudio.pkg" "$SAIDA" || { echo "productbuild falhou"; pausar; exit 1; }
rm -rf "$TMP"

echo
echo "Pronto:  $SAIDA"
echo "No outro Mac: duplo clique no .pkg > Continuar > Instalar. O app abre sozinho no fim."
echo "Primeira vez (sem assinatura da Apple): se o Mac bloquear, Ajustes do Sistema >"
echo "Privacidade e Segurança > 'Abrir Mesmo Assim' (macOS 15+), ou botão direito > Abrir (macOS 14-)."
pausar
