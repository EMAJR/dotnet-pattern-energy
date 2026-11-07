# Campagnes sur Machine 2 (i5-1145G7, Tiger Lake)

## Pourquoi M2

1. **Répliquer le résultat causal (B4)** : aujourd'hui, « site partagé → interaction ; sites
   dédiés → additif » n'est mesuré que sur M1. C'est le résultat central de l'article : il lui
   faut une deuxième microarchitecture.
2. **Donner une deuxième campagne à M2** : +111,9 % est une valeur mono-campagne, sans variance
   inter-campagnes connue, et sans mesure de temps (donc pas d'analyse de la comptabilité de
   l'idle sur M2).
3. **Métadonnées B0** pour le paragraphe de métrologie.

## Préparation (une fois)

Copie sur M2 **tout le dossier `pattern_energy_bench` à jour de M1** (déjà patché, avec tous les
scripts) — c'est plus sûr que de patcher une ancienne copie. Puis :

```bash
cd <chemin>/pattern_energy_bench
python3 patch_phaseB.py          # dira "already patched" si tu as copié depuis M1
dotnet build -c Release && ./bin/Release/net8.0/proto equiv && ./bin/Release/net8.0/proto equivtopo
```

Les deux doivent afficher `ALL EQUIVALENT`. Portable **sur secteur**, couvercle ouvert, aucune
autre application, pas de veille.

## Ordre de lancement

| | commande | durée | priorité |
|---|---|---|---|
| 1 | `bash run_B0_metadata.sh` | ~5 min | indispensable |
| 2 | `bash run_B4_topology.sh` | ~1 h | **indispensable** (réplication causale) |
| 3 | `bash run_replication.sh` | ~2 à 3 h (calcul puis mémoire) | **indispensable** (2ᵉ campagne M2, avec le temps) |
| 4 | `bash run_B1_perf_weights.sh` | ~1 h | utile (travail vs temps sur une 2ᵉ architecture) |
| 5 | `bash run_B4_topology.sh 8 3 mem` | ~1 h 30 | optionnel (topologie en régime mémoire) |

Pour tout enchaîner après B0 :

```bash
bash run_B4_topology.sh && bash run_replication.sh && bash run_B1_perf_weights.sh
```

Les hypothèses de B4 et B1 sont les mêmes que sur M1 et sont affichées avant chaque mesure :
ne pas les modifier.

## À me renvoyer

- `B0_meta_machine2.txt`, `B0_idle_machine2.csv` (le nom suit l'hôte)
- `B4_energy.csv`, `B4_perf.csv`
- `repl_cpu_time.csv`, `repl_mem_time.csv`, `machine_info.txt`
- si lancés : `B1_perf_weights.csv`, `B4_energy_mem.csv`, `B4_perf_mem.csv`

Renomme-les avec un préfixe `M2_` avant de me les envoyer, pour ne pas les confondre avec ceux de
M1 (par exemple `M2_B4_energy.csv`).
