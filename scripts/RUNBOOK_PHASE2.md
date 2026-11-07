# Runbook — Phase 2 : campagne factorielle (7 patrons, 34 configurations)

*Objectif : sur ta machine bare-metal Linux, mesurer l'énergie des 34 compositions sous
les deux régimes (CPU/MEM), calibrer les signatures-ressource, puis ajuster et valider
(LOOCV) la loi de prédiction de `delta_interact`.*

## 0. Pré-requis (rappel Phase 1)
```bash
dotnet --version                     # 8.x
sudo sysctl -w kernel.perf_event_paranoid=0
sudo chmod -R a+r /sys/class/powercap/intel-rapl
```

## 1. Verrouiller l'environnement (avant CHAQUE session)
```bash
sudo cpupower frequency-set -g performance
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo
# ferme navigateur + services non essentiels ; laisse refroidir (< 50 °C).
```

## 2. Build + vérification comportementale (les 34 configs)
```bash
cd pattern_energy_bench
dotnet build -c Release
./bin/Release/net8.0/proto list          # affiche les 34 configurations
./bin/Release/net8.0/proto equiv         # doit dire : ALL EQUIVALENT: 66 configs ... (cpu+mem)
```
> `equiv` garantit la **validité de construit** : les 34 configs (× 2 régimes) reproduisent
> le checksum de la baseline. Sinon, STOP : un patron modifie le résultat (bug de construit).

## 3. Une exécution mesurée (RAPL + proxies GC)
```bash
# combinaison Observer+Memento (all-heap) en régime mémoire, ~5 s, pinnée cœur 3 :
taskset -c 3 ./bin/Release/net8.0/proto run ObMe mem 200000 5
# sortie : energy_J, J_per_op, alloc_per_iter, gen0/gen1/gen2, checksum
```
Les compteurs PMU (branch-misses) se lisent en enveloppant avec perf, comme en Phase 1 :
```bash
perf stat -x, -e branch-misses \
  taskset -c 3 ./bin/Release/net8.0/proto run ObMe mem 200000 5
```

## 4. Campagne factorielle complète (les 34, un régime)
```bash
# écrit une ligne CSV par configuration (34 lignes + entête) :
taskset -c 3 ./bin/Release/net8.0/proto matrix cpu 200000 5 > matrix_cpu.csv
taskset -c 3 ./bin/Release/net8.0/proto matrix mem 200000 5 > matrix_mem.csv
```
Répète la campagne **≥ 30 fois** (boucle externe) en **ordre aléatoire** des configs pour
la robustesse ; agrège par **médiane** et **soustrais l'idle** (voir §5).

```bash
# exemple : 30 réplicats horodatés
for r in $(seq 1 30); do
  taskset -c 3 ./bin/Release/net8.0/proto matrix mem 200000 5 \
    | sed "s/^/$r,/" >> reps_mem.csv          # préfixe le n° de réplicat
  sleep 3
done
```

## 5. Idle (plancher) à soustraire
```bash
# puissance au repos : lis l'énergie RAPL sur ~10 s sans charge, divise par le temps.
# (le prototype Phase-1 avait une routine idle ; sinon : perf stat -e power/energy-pkg/ sleep 10)
```
Énergie dynamique = énergie mesurée − (puissance_idle × temps_fenêtre).

## 6. Analyse (post-traitement Python — Phase 2b)
1. **Signatures (Ordre 0-1)** : pour chaque patron seul, `s_disp` (branch-misses),
   `s_alloc` (alloc_per_iter, gen0/1/2), et `ΔE(DP) = E(DP) − E(base)`.
2. **Interactions (Ordre 2-3)** : `δ = E(combo) − Σ ΔE(DP) − E(base)` ; test permutation +
   seuil de bruit ; classer super-additif / additif / sous-additif.
3. **Loi de prédiction (RQ4)** : ajuster `g_axe` (convexe sur l'axe saturé) sur Ordre 0-1,
   **prédire** Ordre 2-3, évaluer par **LOOCV** le gain de MAE vs modèle additif (δ=0).

## 7. Livrable de fin de Phase 2
- `equiv` OK sur 34 configs × 2 régimes.
- `matrix_cpu.csv` / `matrix_mem.csv` agrégés (≥30 reps, médiane, idle-soustrait).
- Table des signatures-ressource + classement des interactions.
- Loi de prédiction ajustée + score LOOCV (MAE vs naïf) → matière des sections Résultats.

---
**Notes de calibrage** (à ajuster si besoin, documenté dans l'article) :
- `BLOCK=1024`, `SNAP=16`, buffer MEM `1<<16` (512 KiB) — voir constantes en tête de `Program.cs`.
- Si le régime MEM ne sature pas assez le cache (peu de différence CPU/MEM sur les patrons
  heap), augmente le buffer (`MEMBUF`) au-delà du L3, ou allonge `SNAP` pour Memento.
- Codes patrons : St=Strategy De=Decorator Ad=Adapter Fa=Factory Bu=Builder Ob=Observer Me=Memento.
  Un nom de config concatène les codes présents (ex. `ObMe`, `StDeAd`), `base` = Ordre 0.
```
