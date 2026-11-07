# Mesures à lancer sur la Machine 2 (i5-1145G7)

Merci ! Il s'agit de lancer **un seul script**, qui tourne seul pendant environ **4 h 30 à 5 h**
(idéal : le soir, toute la nuit). À la fin, il produit **un seul fichier** à me renvoyer.

---

## 1. Avant de commencer (10 min, une seule fois)

1. **Portable branché sur secteur**, couvercle ouvert, Wi-Fi peut rester actif.
2. **Fermer toutes les applications** (navigateur, mises à jour, Teams, etc.).
3. **Désactiver la mise en veille et le verrouillage d'écran** (Paramètres → Énergie :
   « Jamais »). Le script essaie aussi d'empêcher la veille, mais par sécurité.
4. Vérifier que les outils sont installés (dans un terminal) :

```bash
dotnet --version          # doit afficher 8.x
perf --version
cpupower --help | head -1
```

S'il en manque un :

```bash
sudo apt update
sudo apt install -y dotnet-sdk-8.0 python3 linux-tools-common linux-tools-$(uname -r)
```

## 2. Lancer (2 min)

1. Décompresser `M2_kit.zip` (par exemple dans le dossier personnel).
2. Ouvrir un terminal **dans le dossier `pattern_energy_bench`** du kit, puis :

```bash
bash run_all_M2.sh 2>&1 | tee run_all_M2.log
```

3. Taper le mot de passe `sudo` quand il est demandé (une seule fois, au début).
4. Attendre les premières lignes « B0_metadata » : si on les voit, tout est bon.
   **Ensuite, ne plus toucher la machine** jusqu'à la fin (ni souris, ni clavier, ni autre programme).

Le script vérifie tout seul que la machine est adaptée (pas de machine virtuelle, RAPL
disponible, secteur branché, outils présents). S'il s'arrête au début avec un message `!!`,
il suffit de faire ce que le message indique, puis de relancer la même commande.

## 3. Ce que fait le script (pour information)

| étape | durée | rôle |
|---|---|---|
| préparation, compilation, vérification des résultats | ~3 min | |
| B0 : description de la machine + puissance au repos | ~5 min | |
| B4 : expérience de topologie d'appel | ~1 h | la plus importante |
| campagne de réplication (calcul puis mémoire) | ~2 h 30 | |
| B1 : compteurs matériels à plusieurs charges | ~1 h | |

## 4. À la fin

Le terminal affiche :

```
 DONE in ... min.  Failed steps: none
 Send back this single file:  .../M2_results_AAAAMMJJ.tar.gz
```

**Envoyer ce fichier `M2_results_AAAAMMJJ.tar.gz` à the first author.** C'est tout.

Si une étape a échoué (`Failed steps:` n'est pas `none`), envoyer quand même le fichier : il
contient le journal `M2_run_all_M2.log` qui permet de comprendre ce qui s'est passé.

## En cas de problème

- **Le script s'arrête au début** : lire la ligne qui commence par `!!` et suivre l'indication.
- **La machine s'est mise en veille pendant la nuit** : relancer simplement la commande ;
  les résultats seront refaits depuis le début.
- **Besoin de couper avant la fin** : `Ctrl+C`, puis envoyer quand même le dossier
  `pattern_energy_bench` (ou au moins les fichiers `.csv` et `.txt` qu'il contient).
- **Moins de temps disponible** (environ 3 h 30 au lieu de 5 h) : lancer plutôt
  `NO_B1=1 bash run_all_M2.sh 2>&1 | tee run_all_M2.log` (saute la dernière étape, facultative).
