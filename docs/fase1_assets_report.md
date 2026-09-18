# Fase 1 — Relatório de assets e matting

## Asset selecionado

- **Animal:** capivara
- **Arquivo-fonte:** `assets/source/capybara_walking_pd.gif`
- **Origem:** [Wikimedia Commons — Animal Locomotion Pl.746 - Capybara Walking](https://commons.wikimedia.org/wiki/File:Animal_Locomotion_Pl.746_-_Capybara_Walking.gif)
- **Licença:** domínio público
- **Autoria histórica:** Eadweard Muybridge; reconstrução animada creditada a Avelludo
- **Dimensão:** 846 × 610 px
- **Ciclo original:** 9 frames a 10 fps, 0,9 s
- **Clip preparado para revisão:** `assets/prepared/capybara_matted_5s.gif`, 5,4 s, formado por seis repetições do ciclo de 0,9 s
- **Preview de revisão:** `previews/fase1_capybara_matte.gif`

A escolha é deliberadamente um estudo de locomoção com câmera fixa: o ciclo é claro, repetível e tem variação de pose frame a frame. É um asset de preparação/protótipo, em preto e branco, não uma filmagem natural-colorida. Se a aprovação exigir aparência fotográfica, este clip poderá ser substituído por uma gravação licenciada sem alterar o contrato das máscaras.

## Matting realizado

Script usado: `scripts/prepare_capybara_assets.py`

Saídas:

- `assets/prepared/frames/`: 9 frames completos coalescidos
- `assets/prepared/masks/`: 9 máscaras grayscale, branco = sujeito e preto = fundo
- `assets/prepared/rgba_*.png`: 9 frames com alpha aplicado
- `assets/prepared/capybara_matted_5s.gif`: clip com alpha para uso posterior
- `assets/prepared/manifest.json`: metadados e método reproduzível

Método: conversão para luminância, threshold de 72% invertido para separar a capivara escura do papel claro, seguida de blur de borda de 0,35 px. A máscara é gerada por frame e aplicada como canal alpha; não é filtro visual sobre o vídeo inteiro.

## Checklist de autoverificação

A checklist completa de duplicação ainda não se aplica nesta fase, porque nenhum evento de duplicação foi implementado.

1. **Eventos de duplicação analisados:** 0
2. **Frames de reveal 0%→100%:** N/A — não há reveal nesta fase
3. **Pares de cópias simultâneas com pose idêntica:** N/A — há apenas um sujeito no preview
4. **Distância entre início de duplicação e onset de áudio:** N/A — áudio ainda não foi introduzido
5. **Correlação entre instâncias por segundo e RMS:** N/A — áudio e contagem de instâncias ainda não existem
6. **Primeiro e último frame do trecho preparado:** sim, o ciclo de origem é repetido e não possui cópias extras
7. **Artefato de bloco/retângulo estático sobreposto:** não observado no preview de matte; o campo verde é apenas fundo de inspeção, não parte do asset alpha

## Gate da fase

Os clipes preparados e suas máscaras estão prontos para revisão humana. Não avancei para tracking, composição, áudio ou mecanismo de duplicação.
