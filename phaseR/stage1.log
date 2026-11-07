# Résultats sur le code actuel du noyau (révision 5)

Généré par `analyse_rev5_main.py`. Aucune nouvelle mesure.

## 1. Matrices du code actuel (M1 ET, M2 19/10), B = 20 000

| cellule | E₀ (J / 1000 tâches) | t₀ (s) | * super | * sub | † | rapport SE passes / indép. (médiane) |
|---|---|---|---|---|---|---|
| M1CPU | 7.81 | 1.240 | 10 | 3 | 0 | 0.96 (changements z : aucun) |
| M1MEM | 20.62 | 3.205 | 10 | 8 | 0 | 1.05 (changements z : aucun) |
| M2CPU | 6.77 | 1.747 | 15 | 0 | 0 | 0.97 (changements z : aucun) |
| M2MEM | 16.96 | 4.004 | 10 | 9 | 1 | 1.00 (changements z : aucun) |

Sous-additives * : 20 au total ; toutes avec un patron d'indirection : True. Compositions sans indirection : BuObMe, FaBuMe, BuMe, BuOb, FaBu, FaMe, FaOb, ObMe (toutes ≥ 2 allouants).

## 2. Changements de signe ou d'étoile : septembre (ancien noyau) → code actuel

| cellule | composition | septembre | actuel |
|---|---|---|---|
| M1CPU | AdBu | +8.3† | +4.3 |
| M1CPU | AdMe | +4.9† | -2.2 |
| M1CPU | DeBu | +7.3† | -3.8 |
| M1CPU | DeOb | +6.4* | -2.1 |
| M1CPU | StMe | -4.7† | -10.0* |
| M1CPU | StOb | +5.8† | -14.6* |
| M1CPU | DeAd | +8.9* | +0.4 |
| M1CPU | StDe | -3.6* | +0.3 |
| M1CPU | StDeAd | +4.9† | -3.4 |
| M1MEM | BuObMe | +8.8† | +20.5* |
| M1MEM | FaBuMe | +10.6† | +19.6* |
| M1MEM | AdObMe | +3.0 | +19.1* |
| M1MEM | BuOb | +6.1 | +22.3* |
| M1MEM | FaBu | +7.8 | +23.1* |
| M1MEM | FaMe | +4.8 | +20.2* |
| M1MEM | FaOb | +3.8 | +20.7* |
| M1MEM | ObMe | +5.0 | +19.0* |
| M1MEM | StObMe | -0.4 | +24.9* |
| M1MEM | DeBu | +0.0 | -9.4* |
| M1MEM | DeFa | +0.7 | -7.8* |
| M1MEM | StBu | -4.1 | -9.7* |
| M1MEM | StFa | -4.8 | -3.6* |
| M1MEM | StOb | -5.3 | -3.6* |
| M1MEM | DeAd | -0.6 | -6.8* |
| M1MEM | StDe | -2.3 | -4.0* |
| M1MEM | StDeAd | -6.4† | -6.5* |
| M2CPU | AdBu | +30.7* | +3.8 |
| M2CPU | DeBu | +15.9* | +7.5 |
| M2CPU | DeFa | +12.4* | +0.1 |
| M2CPU | DeMe | +11.9* | -2.3 |
| M2CPU | StOb | +0.8 | +15.5* |
| M2CPU | StDe | +17.6* | +4.6 |
| M2MEM | AdBu | +1.2 | -7.7* |
| M2MEM | AdFa | +0.2 | -7.0* |
| M2MEM | AdMe | +0.5 | -10.9* |
| M2MEM | AdOb | +0.4 | -4.4* |
| M2MEM | DeMe | -0.6 | -3.5† |
| M2MEM | StMe | +0.5 | -8.0* |
| M2MEM | StOb | -0.3 | -5.7* |
| M2MEM | DeAd | -0.1 | -10.6* |
| M2MEM | StAd | -0.6 | -8.3* |
| M2MEM | StDeAd | +0.6 | -9.9* |

## 3. Regroupement des campagnes du code actuel (calcul)

| machine | comp. | k | valeurs | REML + HK [IC 95 %] | DL ± 2SE | τ̂ (REML) | Q (ddl), p | I² | retrait d'une campagne (REML) |
|---|---|---|---|---|---|---|---|---|---|
| M1 | FaBuMe | 8 | +66.7, +62.5, +71.9, +70.7, +72.0, +68.1, +72.5, +72.6 | +69.7 [+65.8 ; +73.5] | +69.8 ± 2.9 | 2.8 | 10.2 (7), 0.18 | 31 % | +68.9 à +71.3 |
| M1 | BuObMe | 7 | +64.6, +65.0, +65.1, +65.5, +65.9, +66.6, +68.0 | +65.7 [+63.2 ; +68.3] | +65.7 ± 2.1 | 0.0 | 0.9 (6), 0.99 | 0 % | +65.4 à +66.0 |
| M1 | BuMe | 9 | +46.2, +38.1, +61.2, +45.2, +43.7, +44.5, +45.2, +44.9, +42.9 | +45.5 [+40.8 ; +50.1] | +45.4 ± 3.5 | 4.5 | 18.8 (8), 0.02 | 57 % | +44.1 à +46.4 |
| M1 | ObMe | 9 | +32.6, +36.5, +41.0, +37.2, +36.0, +35.7, +36.9, +35.9, +36.5 | +35.6 [+33.7 ; +37.5] | +35.6 ± 1.7 | 0.0 | 3.8 (8), 0.87 | 0 % | +35.3 à +36.3 |
| M1 | StDeAd | 8 | -3.4, -2.8, -1.1, +1.9, +0.5, -0.6, -0.3, -0.7 | -0.3 [-3.1 ; +2.4] | -0.3 ± 2.3 | 0.0 | 1.1 (7), 0.99 | 0 % | -0.9 à -0.0 |
| M2 | FaBuMe | 4 | +104.9, +107.4, +96.8, +104.2 | +105.2 [+99.8 ; +110.5] | +105.2 ± 3.4 | 0.0 | 2.4 (3), 0.50 | 0 % | +103.9 à +105.8 |
| M2 | BuObMe | 4 | +91.9, +97.8, +100.7, +99.5 | +96.7 [+90.1 ; +103.3] | +96.6 ± 4.0 | 1.8 | 3.4 (3), 0.34 | 11 % | +95.9 à +98.8 |
| M2 | BuMe | 4 | +54.0, +53.8, +47.4, +58.8 | +54.3 [+47.7 ; +60.9] | +54.2 ± 4.0 | 2.3 | 5.1 (3), 0.16 | 41 % | +52.8 à +55.5 |
| M2 | ObMe | 4 | +54.5, +54.6, +53.4, +56.4 | +54.9 [+51.7 ; +58.2] | +54.9 ± 2.0 | 0.0 | 0.8 (3), 0.84 | 0 % | +54.4 à +55.3 |
| M2 | StDeAd | 4 | +18.3, +19.2, +18.9, +12.5 | +17.9 [+13.0 ; +22.9] | +17.9 ± 3.1 | 0.0 | 2.1 (3), 0.56 | 0 % | +17.3 à +18.8 |

## 4. Sensibilité au code du noyau (A/B, même soirée)

| machine | régime | version | E₀ (J) | t₀ (s) | instr. noyau / itér. | FaBuMe | BuMe | BuObMe | StDeAd |
|---|---|---|---|---|---|---|---|---|---|
| M1 | cpu | old | 6.76 | 1.129 | 33.9 | +100.0 | +59.3 | +85.0 | -7.1 |
| M1 | cpu | new | 7.48 | 1.210 | 42.1 | +62.5 | +38.1 | +65.0 | -2.8 |
| | | z(actuel − ancien) | | | | -4.6 | -4.9 | -3.8 | +0.7 |
| M1 | mem | old | 25.51 | 4.473 | 43.4 | +13.9 | +10.2 | +16.5 | -2.7 |
| M1 | mem | new | 20.73 | 3.199 | 52.5 | +27.3 | +21.3 | +26.9 | -9.2 |
| | | z(actuel − ancien) | | | | +1.1 | +1.7 | +1.8 | -1.9 |
| M2 | cpu | old | 5.96 | 1.613 | 34.0 | +105.4 | +47.4 | +95.5 | +31.6 |
| M2 | cpu | new | 6.49 | 1.747 | 42.1 | +107.4 | +53.8 | +97.8 | +19.2 |
| | | z(actuel − ancien) | | | | +0.3 | +1.8 | +0.5 | -2.7 |
| M2 | mem | old | 51.47 | 15.520 | 43.8 | +8.7 | +5.3 | +8.8 | +1.8 |
| M2 | mem | new | 16.02 | 3.838 | 52.5 | +24.8 | +25.3 | +32.3 | -7.9 |
| | | z(actuel − ancien) | | | | +6.8 | +13.0 | +10.4 | -4.3 |

## 5. Décomposition LMDI de l'interaction (nJ par itération)

Travail = surplus d'instructions × énergie par instruction de la baseline ; coût = variation du temps par instruction ; puissance = variation de E / t (partage LMDI à 2 facteurs de l'énergie par instruction). Somme des trois = ΔE_int exactement.

| cellule | comp. | δ (pts) | E₀ (nJ/itér.) | ΔE_int | travail | coût / instr. | puissance | Δ instr. / itér. |
|---|---|---|---|---|---|---|---|---|
| M1CPU | FaBuMe | +66.7 | 39.1 | +26.1 | +36.4 | -13.4 | +3.1 | +39.2 |
| M1CPU | BuObMe | +64.6 | 39.1 | +25.2 | +36.4 | -16.5 | +5.3 | +39.2 |
| M1CPU | BuMe | +46.2 | 39.1 | +18.0 | +23.3 | -8.1 | +2.8 | +25.1 |
| M1CPU | ObMe | +32.6 | 39.1 | +12.7 | +23.3 | -12.8 | +2.3 | +25.1 |
| M1CPU | StDeAd | -3.4 | 39.1 | -1.3 | -0.0 | +0.1 | -1.4 | -0.0 |
| M1MEM | FaBuMe | +19.6 | 103.1 | +20.2 | +77.3 | -56.0 | -1.1 | +39.4 |
| M1MEM | BuObMe | +20.5 | 103.1 | +21.2 | +76.9 | -54.6 | -1.1 | +39.2 |
| M1MEM | BuMe | +21.5 | 103.1 | +22.1 | +49.3 | -23.1 | -4.1 | +25.1 |
| M1MEM | ObMe | +19.0 | 103.1 | +19.6 | +49.3 | -28.0 | -1.8 | +25.1 |
| M1MEM | StDeAd | -6.5 | 103.1 | -6.7 | +0.2 | -10.4 | +3.5 | +0.1 |
| M2CPU | FaBuMe | +104.9 | 33.8 | +35.5 | +31.4 | +8.2 | -4.1 | +39.1 |
| M2CPU | BuObMe | +91.9 | 33.8 | +31.1 | +31.4 | +6.4 | -6.8 | +39.1 |
| M2CPU | BuMe | +54.0 | 33.8 | +18.3 | +20.2 | +1.6 | -3.5 | +25.1 |
| M2CPU | ObMe | +54.5 | 33.8 | +18.4 | +20.1 | -1.2 | -0.5 | +25.1 |
| M2CPU | StDeAd | +18.3 | 33.8 | +6.2 | +0.0 | +5.2 | +1.0 | +0.0 |
| M2MEM | FaBuMe | +23.9 | 84.8 | +20.2 | +63.2 | -38.5 | -4.4 | +39.1 |
| M2MEM | BuObMe | +34.0 | 84.8 | +28.8 | +63.2 | -34.1 | -0.3 | +39.1 |
| M2MEM | BuMe | +24.5 | 84.8 | +20.8 | +40.6 | -19.6 | -0.2 | +25.1 |
| M2MEM | ObMe | +23.7 | 84.8 | +20.1 | +40.5 | -15.5 | -4.9 | +25.1 |
| M2MEM | StDeAd | -9.9 | 84.8 | -8.4 | -0.0 | -6.5 | -1.9 | -0.0 |

### Les cinq cas « même travail, coût différent »

| cas | configuration | δ (pts) | E₀ (nJ/itér.) | ΔE_int | travail | coût / instr. | puissance | Δ instr. / itér. |
|---|---|---|---|---|---|---|---|---|
| dilution | M1, $W_{\mathrm{CPU}}$ | +66.7 | 39.1 | +26.1 | +36.4 | -13.4 | +3.1 | +39.2 |
| dilution | M1, $W_{\mathrm{MEM}}$ | +19.6 | 103.1 | +20.2 | +77.3 | -56.0 | -1.1 | +39.4 |
| kernel code | M1, previous kernel | +100.0 | 33.8 | +33.8 | +38.9 | -10.5 | +5.4 | +39.0 |
| kernel code | M1, current kernel | +62.5 | 37.4 | +23.4 | +34.7 | -13.1 | +1.7 | +39.1 |
| call-site topology | M2, shared site | +96.8 | 34.1 | +33.0 | +31.7 | +4.1 | -2.8 | +39.2 |
| call-site topology | M2, one site per layer | -22.6 | 33.9 | -7.7 | +0.0 | -7.8 | +0.2 | +0.0 |
| baseline weight | M1, $w = 1$, \texttt{FaBuMe} | +68.1 | 36.5 | +24.9 | +34.0 | -12.7 | +3.5 | +39.2 |
| baseline weight | M1, $w = 1$, \texttt{StDeAd} | -2.2 | 36.5 | -0.8 | -0.0 | -0.2 | -0.6 | -0.0 |
| baseline weight | M1, $w = 8$, \texttt{FaBuMe} | +8.4 | 155.0 | +13.0 | +65.6 | -71.3 | +18.7 | +39.1 |
| baseline weight | M1, $w = 8$, \texttt{StDeAd} | -25.1 | 155.0 | -38.9 | -0.2 | -43.8 | +5.1 | -0.1 |
| duplicated layers | M1, \texttt{Bu}$\times 3$ | +44.2 | 36.2 | +16.0 | +5.3 | +2.5 | +8.2 | +6.2 |
| duplicated layers | M1, \texttt{BuMe} | +45.2 | 36.2 | +16.4 | +21.6 | -9.3 | +4.0 | +25.1 |
| JIT configuration | M1, TC = 0 (measured) | +80.1 | 36.2 | +29.0 | +33.7 | -12.3 | +7.6 | +39.2 |
| JIT configuration | M1, default .NET 8 configuration | +270.3 | 20.2 | +54.6 | +38.6 | +6.5 | +9.5 | +53.1 |

## 6. Signatures, dose-réponse, allocation

| patron | M1CPU | M1MEM | M2CPU | M2MEM |
|---|---|---|---|---|
| St | 1.734 | 1.305 | 1.518 | 1.397 |
| De | 1.330 | 1.168 | 1.293 | 1.229 |
| Ad | 1.925 | 1.486 | 1.786 | 1.668 |
| Fa | 1.502 | 1.273 | 1.313 | 1.312 |
| Bu | 2.445 | 1.976 | 2.332 | 2.160 |
| Ob | 1.582 | 1.329 | 1.364 | 1.458 |
| Me | 1.529 | 1.318 | 1.360 | 1.440 |

| cellule | médianes de groupe 0 / 1 / 2 / 3 allouants [IC 95 % passes] | P(super-linéaire) |
|---|---|---|
| M1CPU | +0.4 [-3.4 ; +3.4] / -2.7 [-5.0 ; -1.2] / +39.9 [+36.0 ; +42.6] / +65.7 [+62.2 ; +69.9] | 0.00 |
| M1MEM | -5.2 [-6.6 ; -3.6] / -2.9 [-4.7 ; -1.6] / +21.1 [+19.1 ; +22.9] / +20.0 [+18.1 ; +25.2] | 0.00 |
| M2CPU | +2.6 [-1.6 ; +6.6] / +2.7 [+0.7 ; +7.0] / +54.1 [+51.8 ; +56.9] / +98.4 [+96.1 ; +104.4] | 0.04 |
| M2MEM | -9.1 [-10.3 ; -7.1] / -3.9 [-5.4 ; -2.9] / +24.1 [+22.6 ; +26.2] / +28.9 [+26.2 ; +31.0] | 0.00 |

| cellule | r(δ, volume) | r(δ, nb. sources) | 3 comp. à 3 250 088 o | 3 comp. à 39 200 o |
|---|---|---|---|---|
| M1CPU | +0.44 | +0.86 | AdBu, DeBu, StBu : -5.2 à +4.3 | AdObMe, ObMe, StObMe : +32.6 à +44.8 |
| M1MEM | +0.29 | +0.84 | AdBu, DeBu, StBu : -9.7 à +0.6 | AdObMe, ObMe, StObMe : +19.0 à +24.9 |
| M2CPU | +0.48 | +0.89 | AdBu, DeBu, StBu : +3.8 à +20.0 | AdObMe, ObMe, StObMe : +47.4 à +54.5 |
| M2MEM | +0.39 | +0.86 | AdBu, DeBu, StBu : -7.7 à -1.3 | AdObMe, ObMe, StObMe : +5.5 à +23.7 |
