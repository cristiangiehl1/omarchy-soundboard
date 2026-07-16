# Omarchy Soundboard

Mesa de sons (soundboard) local no estilo Steam para os arquivos `.mp3` em `~/Music`.
Janela GTK4/libadwaita com grade de botões: clique para tocar (um som por vez),
com busca, controle de volume e "Parar tudo". Reprodução apenas local (sem microfone virtual).

Feito para [Omarchy](https://omarchy.org/) (Arch + Hyprland), mas roda em qualquer
ambiente com GTK4, libadwaita e GStreamer.

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
windowrulev2 = float, class:^(com.omarchy.soundboard)$
windowrulev2 = size 640 480, class:^(com.omarchy.soundboard)$
windowrulev2 = center, class:^(com.omarchy.soundboard)$
bindd = SUPER ALT, S, Mesa de Sons, exec, uwsm-app -- omarchy-soundboard
```

Depois `hyprctl reload`. (`SUPER+ALT+S` foi escolhido por estar livre no Omarchy;
`SUPER+S` é scratchpad e `SUPER+SHIFT+S` é screenshot.)
