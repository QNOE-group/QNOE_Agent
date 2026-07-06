# Repo → Collection Mapping
*Review this before running ingestion. Edit the collection column for any wrong assignments,
then confirm and we'll update `repo_collections.yaml` and run.*

**Collections = which agent's knowledge base the repo goes into:**
- `qtm` — QTM-Agent only
- `photocurrent` — Photocurrent-Agent only
- `qed` — QED-Agent only
- `superconductivity` — Superconductivity-Agent only
- `qsim` — QSIM-Agent only
- `xchiral` — XCHIRAL-Agent only
- `group-wide` — **all agents** (shared tools, docs, multi-team repos)

**Owner = top git contributor (by commit count). Where repo name encodes initials, that person is listed instead.**

---

## Confident mappings ✓

| Repo                                         | Collection          | Owner                        | Reason                                                        |     |
| -------------------------------------------- | ------------------- | ---------------------------- | ------------------------------------------------------------- | --- |
| `QTM_CodeBase`                               | `qtm`               | sergiai                      | "all the code for QTM experiment"                             |     |
| `L208_Opticool`                              | `group-wide`        | Julien Barrier               | L208 is the QTM lab                                           |     |
| `SLG04-PhQH`                                 | `photocurrent`      | Bianca Turini                | SLG = single-layer graphene, PhQH = photocurrent quantum Hall |     |
| `SLG05_PhQH`                                 | `photocurrent`      | Bianca Turini                | same                                                          |     |
| `SLG07-PhQH`                                 | `photocurrent`      | Bianca Turini                | same                                                          |     |
| `SLG09-PhQH`                                 | `photocurrent`      | Bianca Turini                | same                                                          |     |
| `SLG09-C2-PhQH`                              | `photocurrent`      | Bianca Turini                | same                                                          |     |
| `photocurrent-highbias`                      | `photocurrent`      | AWoyke                       | name                                                          |     |
| `GRASP-Acquisition`                          | `group-wide`        | lab-noe (lab account)        | GRASP is in L205 (photocurrent lab)                           |     |
| `GRASP-Analysis`                             | `group-wide`        | Ediz Kaan Herkert            | same                                                          |     |
| `GRASP-TWINS`                                | `group-wide`        | lab-noe (lab account)        | same                                                          |     |
| `FTIR-L205-RapidScan`                        | `qed`               | Abraham Nava                 | L205 is the photocurrent lab                                  |     |
| `BLG-QED`                                    | `qed`               | Abraham Nava                 | "BLG devices related with QED project"                        |     |
| `QED-BLG_Non-local_conductivity-Simulations` | `qed`               | Abraham Nava                 | QED project, optical conductivity + TMM simulations           |     |
| `QED-BLG-literature_surveys`                 | `qed`               | Abraham Nava                 | QED literature                                                |     |
| `QED-BSCCO_X_MoO3-BSCCO_midIR_literature`    | `qed`               | Neha Bhatia                  | QED literature survey                                         |     |
| `QED-kETxhBN`                                | `qed`               | Bianca Turini                | QED project                                                   |     |
| `QED-meeting-notes`                          | `qed`               | Abraham Nava                 | QED team notes                                                |     |
| `QED-phqh`                                   | `qed`               | Bianca Turini                | QED project                                                   |     |
| `RCWA-QED-ZVP`                               | `qed`               | Zoe Velluire-Pellat          | RCWA simulations for QED project                              |     |
| `FCQED-conference-notes`                     | `qed`               | Bianca Turini                | FCQED conference                                              |     |
| `MIT_BLG-hBN_XW003`                          | `photocurrent`      | Xueqiao Wang                 | BLG-hBN device (XW = Xueqiao Wang initials)                   |     |
| `MIT_BLG-hBN_XW423`                          | `photocurrent`      | Paul Jais                    | top git contributor; XW in name = Xueqiao Wang's device       |     |
| `D3-BSCCO-MoO3`                              | `superconductivity` | Lorenzo Orsini / Neha Bhatia | "D3 Device made by Neha" — code by Lorenzo Orsini             |     |
| `MoO3-hBN-MoO3`                              | `group-wide`        | Lorenzo Orsini               | MoO3 material, hyperbolic resonators                          |     |
| `Superconductivity`                          | `superconductivity` | Neha Bhatia                  | name                                                          |     |
| `QSIM_HeFIB`                                 | `qsim`              | Rebecca Hoffmann             | QSIM prefix                                                   |     |
| `QSIM_Patterned_Kagome`                      | `qsim`              | Rebecca Hoffmann             | QSIM prefix                                                   |     |
| `SIM-Meep`                                   | `group-wide`        | Blessy Devassykutty          | MEEP FDTD simulation                                          |     |
| `SIM-kwant-floquet-BdG`                      | `group-wide`        | sergiai                      | kwant simulation (quantum transport)                          |     |
| `gvAI`                                       | `group-wide`        | sergiai                      | condensed matter theory problems, Giuliani & Vignale          |     |
| `QNOE-group-info`                            | `group-wide`        | Bianca Turini                | lab meta-repo — all agents must know this                     |     |
| `NOE_GitHub_tutorial`                        | `group-wide`        | Samy17-AI                    | lab-wide tutorial                                             |     |
| `conference-notes`                           | `group-wide`        | Julien Barrier               | multi-team, general interest                                  |     |
| `QNOE-marimo-examples`                       | `group-wide`        | Bianca Turini                | shared analysis examples                                      |     |
| `SIM-MFLI`                                   | `group-wide`        | Yuval Zamir                  | MFLI lock-in is used across all labs                          |     |
| `SIM-Nbandstructure`                         | `group-wide`        | sergiai                      | band structure tool used across teams                         |     |

---

## Needs your input ⚠️

These repos are ambiguous — I don't have enough context to be confident.

| Repo                      | Owner                       | Description                                                                           | My best guess  | Question                                                                                   |
| ------------------------- | --------------------------- | ------------------------------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------ |
| `Elisa-codes`             | Elisa Mendels               | "PBN 25 and 28 analysis for Cavity QED P10 and normalisation project"                 | `qed`          | Says "Cavity QED" but was listed as photocurrent in original design. Which team owns this? |
| `Polaritons-On_Chip_FTIR` | Lorenzo Orsini              | "on-chip FTIR based on hyperbolic phonon polaritons emission from high-bias graphene" | `group-wide`   | L205 lab (photocurrent), but polaritons are QED territory. Which team?                     |
| `patterned-hBN`           | Bianca Turini               | "hyperbolic phonon polaritons in direct patterned hBN"                                | `group-wide`   | hBN + hyperbolic polaritons → could be superconductivity or QED. Which team owns this?     |
| `sSNOM-TMM`               | Lorenzo Orsini              | "Lorenzo's sSNOM TMM project" — scattering-type SNOM + transfer matrix method         | `group-wide`   | sSNOM is often used for chirality/near-field studies. Is this XCHIRAL? Or another team?    |
| `Bloch`                   | Frank589                    | No description                                                                        | `photocurrent` | Bloch sphere / Bloch equations simulation? Which team?                                     |
| `ChiPy`                   | Ediz Kaan Herkert           | No description                                                                        | `group-wide`   | Name suggests chirality (Chi) + Python. XCHIRAL?                                           |
| `Gr_Optimizer`            | Karuppasamy Soundarapandian | No description                                                                        | `photocurrent` | Graphene optimizer? What does this do and who uses it?                                     |

---

## Action

1. Review the tables above
2. Correct any wrong assignments (especially the ⚠️ section)
3. Tell me your decisions — I'll update `repo_collections.yaml` and we run the dry-run to confirm, then full ingestion
