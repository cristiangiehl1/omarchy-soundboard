# AGENTS.md — Instruções para IA instalar e configurar o omarchy-soundboard

Este arquivo é um runbook para um agente de IA (Claude Code, Codex, etc.) instalar e
configurar o **omarchy-soundboard** numa máquina do usuário. Siga os passos na ordem e
**valide cada etapa** com os comandos indicados antes de seguir. Peça confirmação antes de
editar arquivos de configuração do sistema do usuário (ex.: `~/.config/hypr/`).

## O que é

App gráfico (GTK4 + libadwaita) de "mesa de sons" que toca os `.mp3` de `~/Music` numa grade
de cards, com tema cyberpunk neon, waveform, equalizer reativo ao áudio (GStreamer `spectrum`),
progresso, categorias e busca. Reprodução **apenas local** (nunca roteia para microfone virtual).

- Executável do app: `soundboard.py` (Python, shebang `#!/usr/bin/env python3`).
- Instalador: `install.sh` (cria symlink `~/.local/bin/omarchy-soundboard` → `soundboard.py`
  e copia `omarchy-soundboard.desktop` para o menu). Desinstalador: `uninstall.sh`.
- `application_id` / window class do GTK: **`com.omarchy.soundboard`** (use exatamente isso em
  window rules).

## 1. Pré-requisitos

Alvo: Omarchy / Arch + Hyprland (mas roda em qualquer ambiente com as libs). Verifique:

```bash
# obrigatórios
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); gi.require_version('Gst','1.0'); print('gtk/adw/gst ok')"
gst-inspect-1.0 spectrum >/dev/null && gst-inspect-1.0 playbin >/dev/null && echo "gst plugins ok"
# opcionais (waveform + duração; sem eles o app roda, só não desenha a onda)
command -v ffmpeg && command -v ffprobe
```

Se faltar algo no Arch: `sudo pacman -S --needed python-gobject gtk4 libadwaita gstreamer gst-plugins-base gst-plugins-good ffmpeg`.
(No Omarchy padrão, tudo isso já vem instalado.)

## 2. Instalar

```bash
git clone git@github.com:cristiangiehl1/omarchy-soundboard.git ~/omarchy-soundboard
cd ~/omarchy-soundboard
./install.sh
```

Valide:

```bash
ls -l ~/.local/bin/omarchy-soundboard              # deve ser symlink -> .../soundboard.py
test -f ~/.local/share/applications/omarchy-soundboard.desktop && echo "desktop ok"
case ":$PATH:" in *":$HOME/.local/bin:"*) echo "PATH ok";; *) echo "ADICIONE ~/.local/bin ao PATH";; esac
```

Coloque arquivos `.mp3` em `~/Music`. Teste sem travar a sessão (o `timeout` encerra em 3s;
`exit=124` = sucesso; traceback = investigar):

```bash
timeout 3 omarchy-soundboard; echo "exit=$?"
```

## 3. Configurar atalho no Hyprland (opcional — CONFIRME com o usuário antes de editar)

Este passo edita `~/.config/hypr/bindings.conf`. **Só faça com autorização do usuário.**

### 3a. Faça backup

```bash
cp ~/.config/hypr/bindings.conf ~/.config/hypr/bindings.conf.bak.$(date +%s)
```

### 3b. ESCOLHA UM ATALHO LIVRE — não assuma

⚠️ Lição aprendida: no Omarchy, muitos combos com `S` já são usados
(`SUPER+S` = scratchpad, `SUPER+SHIFT+S` = screenshot, `SUPER+ALT+S` = mover pro scratchpad).
**Sempre verifique** antes de bindar. Liste TODOS os binds já carregados (inclui os defaults
do Omarchy que o `hyprland.conf` faz `source`):

```bash
# lista binds dos arquivos realmente carregados
grep -rhoiE '^\s*bind[a-z]*\s*=\s*[A-Z ]+,\s*[A-Za-z0-9]+' \
  ~/.config/hypr/bindings.conf \
  ~/.local/share/omarchy/default/hypr/bindings/*.conf \
  ~/.local/share/omarchy/default/hypr/windows.conf | sed -E 's/^\s*bind[a-z]*\s*=\s*//' | sort -u
```

Escolha um combo que NÃO apareça na lista. Default recomendado: **`SUPER, A`** ("A" de Audio),
que costuma estar livre no Omarchy. Confirme:

```bash
COMBO="SUPER, A"   # ajuste se necessário
grep -rhiE "^\s*bind[a-z]*\s*=\s*${COMBO}\s*," \
  ~/.config/hypr/bindings.conf ~/.local/share/omarchy/default/hypr/**/*.conf 2>/dev/null \
  && echo "OCUPADO — escolha outro" || echo "livre"
```

### 3c. Acrescente as linhas (sintaxe do Hyprland 0.55+)

⚠️ Lição aprendida: a sintaxe atual é `windowrule = <regra>, match:class ...`, e regras
booleanas precisam de valor: **`float on`**, **`center on`** (NÃO `float`/`center` sozinhos, e
NÃO `windowrulev2`). Ajuste a tecla do `bindd` para o combo que você validou:

```conf
# Mesa de Sons (omarchy-soundboard)
windowrule = float on, match:class ^(com\.omarchy\.soundboard)$
windowrule = size 640 480, match:class ^(com\.omarchy\.soundboard)$
windowrule = center on, match:class ^(com\.omarchy\.soundboard)$
bindd = SUPER, A, Mesa de Sons, exec, uwsm-app -- omarchy-soundboard
```

### 3d. Recarregue e VALIDE (obrigatório)

```bash
hyprctl reload
hyprctl configerrors    # DEVE sair vazio; se houver erro, corrija a sintaxe e repita
```

Se `configerrors` acusar `invalid field float: missing a value`, você esqueceu o `on`.

## 4. Verificação final

- `omarchy-soundboard` abre uma janela flutuante centralizada com os sons de `~/Music`.
- Pelo atalho: aperte o combo escolhido; a janela deve aparecer (class `com.omarchy.soundboard`).
- Clique num card: toca (um som por vez), o card pulsa e vira equalizer, a barra de progresso anda.

Checagem da janela via Hyprland:

```bash
hyprctl clients | grep -A1 'class: com.omarchy.soundboard'
```

## 5. Atualizar / desinstalar

```bash
cd ~/omarchy-soundboard && git pull        # atualizar (o symlink já aponta pro código novo)
./uninstall.sh                             # remove launcher e .desktop (não apaga o repo)
```

## Regras para o agente

- **Nunca** configure roteamento para microfone virtual — o design é reprodução local.
- **Nunca** edite `~/.local/share/omarchy/` (fonte do Omarchy, gerenciada por update).
- Ao editar `~/.config/hypr/`, faça backup, valide com `hyprctl configerrors`, e informe o
  usuário qual tecla foi usada e por quê.
- Waybar **não** recarrega sozinho; se algum dia adicionar um módulo, rode `omarchy restart waybar`.
- Só afirme "instalado/funcionando" após rodar os comandos de verificação e ver a saída esperada.
