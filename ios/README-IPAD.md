# Guide de Déploiement Flotte iPad — Belle Vitesse Admin

Ce guide explique comment compiler l'application native **Belle Vitesse Admin** pour iPadOS et la déployer sur la flotte de tablettes (3 à 10 iPads pour techniciens, pilotes et direction) à l'aide d'**Apple Configurator 2** ou directement via **Xcode**.

---

## 1. Caractéristiques de l'Application

* **Architecture** : Application iPadOS native (SwiftUI + `WKWebView`) ciblant **iPadOS 16.0 et supérieur**.
* **Sécurité Biométrique** : Verrouillage et déverrouillage par **Face ID** ou **Touch ID** avec repli sur le code iPad. Verrouillage automatique dès que l'application passe en arrière-plan pour sécuriser les données sur plateau.
* **Support Apple Pencil & Tactile** : Désactivation des gestes de scroll parasites lors du tracé sur les canvas de signature (décharges pilotes & productions) et d'annotation de dégâts/impacts carrosserie.
* **Appareil Photo Natif** : Prise de vue directe lors des Check-ins, Check-outs et déclarations d'incidents.
* **Passerelle Haptique** : Vibrations de confirmation haptiques natives lors des enregistrements réussis.
* **Sélecteur d'Environnement** : Bascule facile entre la production (`https://team.bellevitesse.com/admin`) et un serveur de test/local via la barre d'outils flottante.

---

## 2. Prérequis sur votre Mac

1. **Xcode** (version 15 ou supérieure, déjà installé sur votre Mac).
2. **Apple Configurator** (téléchargeable gratuitement depuis le **Mac App Store**).
3. Un câble USB / USB-C ou un hub multiport USB pour brancher vos iPads.

---

## 3. Configuration et Signature dans Xcode

1. Ouvrez le projet dans Xcode en double-cliquant sur le fichier :
   ```bash
   ios/BelleVitesseAdmin.xcodeproj
   ```
2. Dans la colonne de gauche de Xcode, cliquez sur la racine du projet **BelleVitesseAdmin**.
3. Allez dans l'onglet **Signing & Capabilities** :
   * Cochez **Automatically manage signing**.
   * Dans **Team**, sélectionnez votre compte Apple (votre Apple ID personnel gratuit suffit pour le développement ou votre compte entreprise).
   * Le Bundle Identifier est préconfiguré sur : `com.bellevitesse.admin`.

---

## 4. Déploiement en Masse via Apple Configurator 2 (Recommandé)

Cette méthode permet d'installer l'application en quelques secondes sur vos 3 à 10 iPads en même temps sans passer par l'App Store.

### Étape A : Générer le fichier d'installation (.ipa)
1. Dans Xcode, dans le menu déroulant des cibles (en haut au centre), sélectionnez **Any iOS Device (arm64)**.
2. Dans la barre de menus, cliquez sur **Product > Archive**.
3. Une fois l'archive terminée (la fenêtre *Organizer* s'ouvre automatiquement) :
   * Cliquez sur le bouton bleu **Distribute App**.
   * Choisissez **Development** (ou *Enterprise* si vous possédez un compte Apple Developer Entreprise).
   * Conservez les options par défaut et cliquez sur **Next** jusqu'à l'étape finale.
   * Cliquez sur **Export** et enregistrez le dossier sur votre bureau. Il contient le fichier `BelleVitesseAdmin.ipa`.

### Étape B : Installer sur la flotte d'iPads
1. Lancez **Apple Configurator** sur votre Mac.
2. Branchez vos 3 à 10 iPads à votre Mac (idéalement via un hub USB multiple).
3. Vos iPads apparaissent tous sur l'écran d'Apple Configurator.
4. Sélectionnez tous vos iPads (`Cmd + A`).
5. Glissez-déposez simplement le fichier `BelleVitesseAdmin.ipa` sur les iPads sélectionnés.
6. Cliquez sur **Ajouter** / **Installer** : l'application s'installe simultanément sur tous les iPads !

> [!TIP]
> **Première ouverture sur un iPad avec compte gratuit Apple :**
> Si c'est la première fois que vous installez une application signée avec votre Apple ID sur cet iPad, allez sur l'iPad dans :
> **Réglages > Général > VPN et gestion des appareils > Votre Compte > Faire confiance**.
> Cette manipulation n'est requise qu'une seule fois par iPad.

---

## 5. Alternative : Installation Rapide unitaire via Câble USB

Pour tester immédiatement sur un iPad en direct :
1. Branchez l'iPad en USB sur votre Mac.
2. Déverrouillez l'iPad et choisissez *"Faire confiance à cet ordinateur"*.
3. Dans Xcode, dans le sélecteur d'appareil en haut, choisissez votre iPad physique.
4. Appuyez sur le bouton **Play (▶️)** ou `Cmd + R` : Xcode compile, installe et lance directement l'application sur l'iPad.

---

## 6. Utilisation sur le Terrain & Astuces

* **Déverrouillage Face ID / Touch ID** : Dès l'ouverture, l'iPad sollicite le capteur biométrique. En cas d'échec (ex: masque ou gant), l'iPad propose de saisir le code de verrouillage de la tablette.
* **Barre d'outils flottante (icône curseur en bas à droite)** :
  * 🔄 **Recharger** : Rafraîchit la page courante en cas de retour réseau après une zone blanche.
  * ⚙️ **Réglages** : Permet de basculer vers un serveur de staging ou de désactiver le verrouillage automatique.
  * 🔒 **Verrouiller** : Verrouille instantanément l'application avant de prêter la tablette à un client ou un intervenant externe.
* **Navigation responsive** : Le bouton hamburger en haut à gauche ouvre le menu complet sans empiéter sur l'espace d'affichage des fiches projets et des véhicules.

---

## 7. Authentification Magic Link par Liens Universels (Universal Links)

L'application prend en charge les **Universal Links Apple** :
* Lorsqu'un utilisateur demande un lien magique de connexion depuis l'iPad (ou reçoit l'email `https://team.bellevitesse.com/admin/auth/<token>`), un tap sur ce lien dans Mail/Gmail **ouvre directement l'application Belle Vitesse Admin** sans passer par Safari.
* **Côté serveur** : Flask sert automatiquement le fichier d'association Apple à l'adresse `/.well-known/apple-app-site-association`.
* **Côté app iPad** : Le droit `com.apple.developer.associated-domains` est configuré sur `applinks:team.bellevitesse.com` et l'écouteur `.onOpenURL` dans Swift valide le jeton et connecte immédiatement l'utilisateur.

