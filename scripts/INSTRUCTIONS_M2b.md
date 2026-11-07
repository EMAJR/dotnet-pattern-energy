# Machine 2 — deuxième série de mesures (~3 h)

Merci encore ! Même principe que la dernière fois : **une seule commande**, puis on ne touche plus
la machine. Elle produit **un seul fichier** à renvoyer.

## Avant de lancer

- Portable **sur secteur**, couvercle ouvert, **profil d'énergie `performance`** (comme la dernière
  fois — ne rien changer d'autre), veille et verrouillage désactivés, aucune autre application.
- Décompresser `M2b_kit.zip` (un nouveau dossier, ne pas réutiliser l'ancien).

## Lancer

Dans un terminal, **dans le dossier `pattern_energy_bench` du nouveau kit** :

```bash
bash run_all_M2b.sh 2>&1 | tee run_all_M2b.log
```

Taper le mot de passe `sudo` au début. Quand « pre-flight OK » puis « build + equivalence OK »
s'affichent, tout est bon : ne plus toucher la machine.

## Ce que fait le script

| étape | durée |
|---|---|
| vérifications + compilation | ~3 min |
| comparaison ancien code / nouveau code, en alternance | ~1 h 45 |
| expérience de topologie (2ᵉ fois) | ~1 h |

## À la fin

Le terminal affiche `DONE in … min. Failed steps: none` et le chemin de
**`M2b_results_AAAAMMJJ.tar.gz`** : l'envoyer à the first author (même si une étape a échoué).

En cas de message `!!` au début : faire ce qu'il indique, puis relancer la même commande ; ou
envoyer une photo de l'écran.
