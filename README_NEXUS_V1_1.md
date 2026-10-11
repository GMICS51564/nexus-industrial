# NEXUS Industrial V1.1 — schéma renforcé et données synthétiques

## Contenu
- `nexus_industrial_schema_v1_1.sql` : schéma V1 + patch V1.1, index, triggers et migration versionnée.
- `nexus_industrial_seed_v1_1.sql` : export complet des données de démonstration. À appliquer sur une base vide après le schéma.
- `nexus_industrial_demo_v1_1.sqlite` : base SQLite prête à explorer.
- `nexus_six_week_production.csv` : un enregistrement par ordre synthétique, utile pour les graphiques.
- `test_nexus_v1_1.py` : tests de régression.
- `nexus_v1_1_validation_report.txt` : métriques et contrôles.

## Période
Du 2026-08-31 au 2026-10-09 inclus, 30 jours ouvrés, 30 ordres synthétiques additionnels.

## Durcissements V1.1
- Index unique partiel pour empêcher les doubles affectations de rôle global lorsque `scope_id IS NULL`.
- Index ciblés sur le suivi de production, les arrêts, les écarts, les contrôles qualité, les non-conformités et les mesures de bénéfice.
- Triggers de cohérence entre ordre, opération, plan de contrôle et non-conformité.
- Migration enregistrée en version 2.

## Connexion SQLite
Activer les clés étrangères dans chaque connexion : `PRAGMA foreign_keys = ON;` SQLite ne l'active pas globalement par défaut.

## Données et interprétation
Tout est fictif et ne représente ni Framatome ni un site industriel réel. La phase après amélioration est scénarisée pour montrer comment comparer des périodes; elle ne prouve aucun gain réel.

## Exécution des tests
`python test_nexus_v1_1.py`

## Recréation
`python build_nexus_v11.py` régénère le schéma, la base, le seed, le CSV et le rapport à partir des fichiers V1 présents dans le même dossier.
