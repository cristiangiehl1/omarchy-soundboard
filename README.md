# Omarchy Soundboard

Mesa de sons (soundboard) local no estilo Steam para os arquivos `.mp3` em `~/Music`.
Janela GTK4/libadwaita com grade de botões: clique para tocar (um som por vez),
com busca, controle de volume e "Parar tudo". Reprodução apenas local (sem microfone virtual).
Visual **cyberpunk neon** embutido (paleta violeta/magenta/cyan, glow nos botões), no mesmo
estilo do tema [omarchy-cyberpunk-neon](https://github.com/cristiangiehl1/omarchy-cyberpunk-neon).

Feito para [Omarchy](https://omarchy.org/) (Arch + Hyprland), mas roda em qualquer
ambiente com GTK4, libadwaita e GStreamer.

## Recursos

- **Cards por som** com categoria automática (Games/Anime/Memes/Música/Outros) e cor de destaque.
- **Waveform** de cada arquivo desenhado no card (via ffmpeg) + **duração**.
- **Equalizer reativo ao áudio**: o card que está tocando vira um espectro neon em tempo real (GStreamer `spectrum`).
- **Barra de progresso** no card enquanto toca; **um som por vez** (novo corta o anterior).
- **Fundo synthwave** animado (grade em perspectiva + sol neon + scanlines CRT, via Cairo).
- **Filtro por categoria** (chips) + **busca** com estado "nenhum resultado".
- **Volume ao vivo**, **Parar tudo**, **atualizar pasta**, e animações neon (pulso ao tocar, glow, título).

> Requer `ffmpeg`/`ffprobe` para waveform e duração (opcional — sem eles o app funciona,
> só não mostra a forma de onda). No Omarchy/Arch já vêm instalados.

## Requisitos

- Python 3, PyGObject (`gi`), GTK 4, libadwaita, GStreamer 1.0 + `gst-plugins-good`/`gst-plugins-base`.
  (No Omarchy/Arch: já vêm instalados por padrão.)

## Instalação

```bash
git clone https://github.com/cristiangiehl1/omarchy-soundboard
cd omarchy-soundboard
./install.sh
```

Isso cria o comando `omarchy-soundboard` (symlink em `~/.local/bin/`) e adiciona o app ao menu.
Coloque seus `.mp3` em `~/Music` e rode `omarchy-soundboard`.

Para remover: `./uninstall.sh`.

## Atalho no Hyprland (opcional)

Adicione ao seu `~/.config/hypr/bindings.conf`:

```conf
# Mesa de Sons (soundboard)
windowrule = float on, match:class ^(com\.omarchy\.soundboard)$
windowrule = size 640 480, match:class ^(com\.omarchy\.soundboard)$
windowrule = center on, match:class ^(com\.omarchy\.soundboard)$
bindd = SUPER, A, Mesa de Sons, exec, uwsm-app -- omarchy-soundboard
```

Depois `hyprctl reload`. (`SUPER+A` — "A" de Audio — foi escolhido por estar livre no
Omarchy; as variações de `S` já são usadas pelo scratchpad.) A sintaxe `windowrule =
..., match:...` é a do Hyprland 0.55+.
