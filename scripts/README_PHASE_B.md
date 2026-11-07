# Phase B — à lancer sur Machine 1 (B0 aussi sur Machine 2)

## Fichiers à copier dans `pattern_energy_bench/` sur M1

`patch_phaseB.py` · `phaseB_common.sh` · `run_B0_metadata.sh` · `run_B1_perf_weights.sh` ·
`run_B2_mechanism.sh` · `run_B3_tiered.sh` · `run_B4_topology.sh`

## Une seule fois : patcher et vérifier

```bash
cd ~/Desktop/"pattern_energy_bench (8)"/pattern_energy_bench
python3 patch_phaseB.py
dotnet build -c Release && ./bin/Release/net8.0/proto equiv && ./bin/Release/net8.0/proto equivtopo
```

Les deux doivent afficher `ALL EQUIVALENT`. Si la compilation échoue, **arrête et envoie-moi
l'erreur** : je n'ai pas pu compiler de mon côté (pas de .NET dans mon environnement), j'ai
seulement vérifié la syntaxe à la main. Le patch ne modifie aucune commande existante
(`runk`, `runkdup`, `matrixk`, `equiv`) : il ajoute `runktopo` et `equivtopo`.

## Ordre et durée

| | Script | Durée | Ce que ça tranche |
|---|---|---|---|
| 1 | `bash run_B0_metadata.sh` (M1 **et** M2) | ~5 min | domaines RAPL, Turbo, versions, P_idle |
| 2 | `bash run_B1_perf_weights.sh` | ~1 h | le point (4) de §4.5 (H1 / H2 / H3) |
| 3 | `bash run_B2_mechanism.sh` | ~20 min | VSD ou GDV |
| 4 | `bash run_B3_tiered.sh` | ~1 h | l'effet survit-il à la config .NET par défaut ? |
| 5 | `bash run_B4_topology.sh` | ~1 h | le confondant topologie / catégorie de patron |

Après B0, tu peux tout enchaîner d'un coup (≈ 3 h 30) :

```bash
bash run_B1_perf_weights.sh && bash run_B2_mechanism.sh && bash run_B3_tiered.sh && bash run_B4_topology.sh
```

Conditions : portable **sur secteur**, couvercle ouvert, aucune autre application, pas de mise
en veille. Chaque script verrouille le gouverneur et le Turbo et s'arrête tout seul si une
vérification échoue (compilation, équivalence, gouverneur, RAPL, perf).

## Ce qu'il faut me renvoyer

- `B0_meta_<hôte>.txt`, `B0_idle_<hôte>.csv` (des deux machines)
- `B1_perf_weights.csv`
- `B2_out.tgz`
- `B3_energy.csv`, `B3_perf.csv`
- `B4_energy.csv`, `B4_perf.csv`

Chaque script affiche ses hypothèses **avant** de mesurer. Ne les modifie pas après coup :
c'est ce qui fait de ces expériences des tests et pas des illustrations.
