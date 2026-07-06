# Suspected Papers for Docling Re-indexing — Manual Review

Files detected as likely academic papers by content heuristics (Abstract + email/affiliation signals).
These were indexed with pypdf only (fast path). Mark `YES` for ones that should get Docling re-processing.

**Instructions:** Add a `YES` or `NO` after each filename. Then run:
```bash
# Re-index confirmed papers with Docling
DOCLING_DEVICE=cuda PYTHONPATH=/opt/qnoe-agent ... python -m agent.ingest.ingest_all --force-ext .pdf --paper-list /path/to/confirmed.txt
```
*(Tool to be built — see TODO)*

---

## Manuscripts (315 files)

| #   | File                                                                                                            | Paper? |
| --- | --------------------------------------------------------------------------------------------------------------- | ------ |
| 1   | `2016 NMat  Thermoelectric plasmon detection/bib-files/Persson2010.pdf`                                         | Y      |
| 2   | `2016 NMat  Thermoelectric plasmon detection/bib-files/Ramezanali2009.pdf`                                      | Y      |
| 3   | `2016 NMat  Thermoelectric plasmon detection/long notes.pdf`                                                    |        |
| 4   | `2016 NMat  Thermoelectric plasmon detection/nearfieldthermal.pdf`                                              | Y      |
| 5   | `2017 Nonlocal plasmons/Analysis/toymodels/conductivity_nonlocal.pdf`                                           | Y      |
| 6   | `2017 Nonlocal plasmons/bib-files/Ramezanali2009.pdf`                                                           | Y      |
| 7   | `2017 Reciprocity/reciprocity.pdf`                                                                              |        |
| 8   | `2018 NanoLetters_THz_photodetection/Arxiv_version/THz_PTE_photodetector_Arxiv_version.pdf`                     | Y      |
| 9   | `2018 NanoLetters_THz_photodetection/Submitted_revised_version_NanoLett/THz_PTE_photodetector_rev_v7.pdf`       |        |
| 10  | `2019_2D-3D integration of hBN.../bib-files/Persson2010.pdf`                                                    | Y      |
| 11  | `2019_2D-3D integration of hBN.../bib-files/Ramezanali2009.pdf`                                                 | Y      |
| 12  | `2019_mid-IR_photodetection.../Input_collaborators/MIR_PD_v2-EL_SC_implemented.pdf`                             |        |
| 13  | `2019_mid-IR_photodetection.../Input_collaborators/MIR_PTE_photodetector_Arxiv_version.pdf`                     |        |
| 14  | `2019_mid-IR_photodetection.../Input_collaborators/MIR_PTE_photodetector_Arxiv_version_v53_FK_EL.pdf`           |        |
| 15  | `2019_mid-IR_photodetection.../Input_collaborators/MIR_PTE_photodetector_Arxiv_version_v53_FK_ELimplemnted.pdf` | Y      |
| 16  | `2019_mid-IR_photodetection.../old_Version_2020/MIR_PTE_photodetector_Arxiv_version_v52_FK_EL.pdf`              |        |
| 17  | `2019_mid-IR_photodetection.../old_Version_2020/MIR_PTE_photodetector_Arxiv_version_v53_FK_EL.pdf`              |        |
| 18  | `2019_mid-IR_photodetection.../old_Version_2020/MIR_PTE_photodetector_Arxiv_version_v54_FK_EL.pdf`              |        |
| 19  | `2019_mid-IR_photodetection.../old_Version_2020/MIR_PTE_photodetector_Arxiv_version_v55.pdf`                    |        |
| 20  | `2024_Electrical_Spectroscopy_Sebastian/Plasmonic_main_text_with_remarks.pdf`                                   |        |
| 21  | `2024_Electrical_Spectroscopy_Sebastian/Plasmonic_main_text_wo_remarks.pdf`                                     |        |
| 22  | `ACSNano_Ribbon/ribbons-5.pdf`                                                                                  |        |
| 23  | `ACSNano_Ribbon/ribbons.pdf`                                                                                    |        |
| 24  | `Achim/cvd-nearfield-pc-paper/ncomms_manuscript_checklist.pdf`                                                  |        |
| 25  | `Achim/mid-IR-paper/MIDIR_pc_arxiveformat.pdf`                                                                  |        |
| 26  | `ControllingEnergyRelaxation/CompetingEnergyRelaxationGraphene.pdf`                                             |        |
| 27  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_18 copy.pdf`                                           |        |
| 28  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_18_Frank.pdf`                                          |        |
| 29  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_20 copy 2_Frank.pdf`                                   |        |
| 30  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_23.pdf`                                                |        |
| 31  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_24_Frank.pdf`                                          |        |
| 32  | `ControllingEnergyRelaxation/ControllingEnergyRelaxation_26.pdf`                                                | Y      |
| 33  | `DBT_transfer/graphene_ruler_CT_fsc-1_ARP_FK - annotated.pdf`                                                   |        |
| 34  | `DBT_transfer/graphene_ruler_CT_fsc-1_ARP_FK.pdf`                                                               |        |
| 35  | `DBT_transfer/graphene_ruler_work_CT_G - annotated.pdf`                                                         |        |
| 36  | `DBT_transfer/graphene_ruler_work_CT_G.pdf`                                                                     |        |
| 37  | `DBT_transfer/graphene_ruler_work_CT_G_ARPpos_7May.pdf`                                                         |        |
| 38  | `Dissociation Stark effect WSe2/Paper Dissociation/old/1409.0300.pdf`                                           |        |
| 39  | `Energytransfer_gating/Erbium_11 copy 2.pdf`                                                                    |        |
| 40  | `Energytransfer_gating/Erbium_12.pdf`                                                                           |        |
| 41  | `Energytransfer_gating/Erbium_12_Frank.pdf`                                                                     |        |
| 42  | `Energytransfer_gating/Erbium_13.pdf`                                                                           |        |
| 43  | `Energytransfer_gating/Erbium_14 - annotated.pdf`                                                               |        |
| 44  | `Energytransfer_gating/Erbium_16.pdf`                                                                           |        |
| 45  | `Energytransfer_gating/Erbium_17.pdf`                                                                           |        |
| 46  | `Energytransfer_gating/Erbium_21_commentsFrank.pdf`                                                             |        |
| 47  | `Energytransfer_gating/Erbium_24-Frank.pdf`                                                                     |        |
| 48  | `Energytransfer_gating/Erbium_24.pdf`                                                                           |        |
| 49  | `Energytransfer_gating/Erbium_27.pdf`                                                                           |        |
| 50  | `Energytransfer_gating/Erbium_28.pdf`                                                                           |        |
| 51  | `Energytransfer_gating/Erbium_31.pdf`                                                                           |        |
| 52  | `Energytransfer_gating/Erbium_33.pdf`                                                                           | Y      |
| 53  | `Energytransfer_gating/Erbium_5_Frank.pdf`                                                                      |        |
| 54  | `Energytransfer_gating/Erbium_9.pdf`                                                                            |        |
| 55  | `Energytransfer_gating/Erbium_Graphene_1.pdf`                                                                   |        |
| 56  | `Energytransfer_gating/Proofs/www.nature.com-licenceforms-npg-mpl-ltp.pdf copy.pdf`                             | Y      |
| 57  | `Energytransfer_gating/graphene_ruler - annotated.pdf`                                                          |        |
| 58  | `Energytransfer_gating/graphene_ruler.pdf`                                                                      |        |
| 59  | `Energytransfer_gating/resubmission/Erbium_46 FK.pdf`                                                           |        |
| 60  | `Energytransfer_gating/resubmission/Erbium_47_FK.pdf`                                                           | Y      |
| 61  | `Hybrid Plasmon Photonics (GOLD)/HPPPaper_v1/Acoustic_Plasmons_v1.pdf`                                          |        |
| 62  | `Hybrid Plasmon Photonics (GOLD)/HPPPaper_v1/achemso/achemso-demo.pdf`                                          |        |
| 63  | `Hybrid Plasmon Photonics (GOLD)/HPPPaper_v1/achemso/achemso.pdf`                                               |        |
| 64  | `Hybrid Plasmon Photonics (GOLD)/HppPaper_v1b/Acoustic_Plasmons_v1.pdf`                                         |        |
| 65  | `Hybrid Plasmon Photonics (GOLD)/HppPaper_v2/Acoustic_Plasmons_v2.pdf`                                          |        |
| 66  | `Hybrid Plasmon Photonics (GOLD)/HppPaper_v3/Acoustic_Plasmons_v2.pdf`                                          |        |
| 67  | `Hybrid Plasmon Photonics (GOLD)/HppPaper_v3/Acoustic_Plasmons_v3_test.pdf`                                     | Y      |
| 68  | `IR Photodetection/Corrections nanoletters/MIDIR_pc_vrev.pdf`                                                   |        |
| 69  | `IR Photodetection/Corrections nanoletters/proof_MB.pdf`                                                        |        |
| 70  | `IR Photodetection/Corrections nanoletters/referee/MIDIR_pc_vrev_blue.pdf`                                      |        |
| 71  | `IR Photodetection/Corrections nanoletters/version_main_blue/MIDIR_pc_vrev_blue.pdf`                            |        |
| 72  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/Louis/Lifetime-control_final_v2.pdf`                       | Y      |
| 73  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v0/MIDIR_pc.pdf`                                  |        |
| 74  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v1/MIDIR_pc_v1.pdf`                               |        |
| 75  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v1/MIDIR_pc_v1_Frank.pdf`                         |        |
| 76  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v10/MIDIR_pc_v10.pdf`                             | Y      |
| 77  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v2/MIDIR_pc_v2.pdf`                               |        |
| 78  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v3/MIDIR_pc_v3_FK.pdf`                            |        |
| 79  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v7/MIDIR_pc_v7.pdf`                               |        |
| 80  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v8/MIDIR_pc_v8.pdf`                               |        |
| 81  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v9/MIDIR_pc_v9.pdf`                               |        |
| 82  | `IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/vfinal/MIDIR_pc_vfinal.pdf`                       |        |
| 83  | `IR Photodetection/submission_nanoletters/vfinal/MIDIR_pc_vfinal.pdf`                                           |        |
| 84  | `Lifetime_control/2nd round galley proofs.pdf`                                                                  |        |
| 85  | `Lifetime_control/versions/final_v0/Lifetime-control_final_v0.pdf`                                              |        |
| 86  | `Lifetime_control/versions/final_v1/Lifetime-control_final_v1.pdf`                                              |        |
| 87  | `Lifetime_control/versions/final_v2/Gaudreau_graphene.pdf`                                                      |        |
| 88  | `Lifetime_control/versions/final_v2/Lifetime-control_final_v2.pdf`                                              |        |
| 89  | `Lifetime_control/versions/v1/Lifetime control_v1.pdf`                                                          |        |
| 90  | `Lifetime_control/versions/v10/Lifetime control_v10.pdf`                                                        |        |
| 91  | `Lifetime_control/versions/v11/Lifetime control_v11.pdf`                                                        |        |
| 92  | `Lifetime_control/versions/v12/Lifetime control_v12.pdf`                                                        |        |
| 93  | `Lifetime_control/versions/v13/Lifetime control_v13.pdf`                                                        |        |
| 94  | `Lifetime_control/versions/v14/Lifetime control_v14.pdf`                                                        |        |
| 95  | `Lifetime_control/versions/v14/Lifetime control_v14_KJT.pdf`                                                    |        |
| 96  | `Lifetime_control/versions/v15/Lifetime control_v15.pdf`                                                        |        |
| 97  | `Lifetime_control/versions/v16/Lifetime control_v16.pdf`                                                        |        |
| 98  | `Lifetime_control/versions/v17/Lifetime control_v17.pdf`                                                        |        |
| 99  | `Lifetime_control/versions/v18/Lifetime control_v18.pdf`                                                        |        |
| 100 | `Lifetime_control/versions/v19/Lifetime control_v19.pdf`                                                        |        |
| 101 | `Lifetime_control/versions/v20/Lifetime control_v20.pdf`                                                        |        |
| 102 | `Lifetime_control/versions/v21/Lifetime control_v21.pdf`                                                        |        |
| 103 | `Lifetime_control/versions/v22/Lifetime control_v22.pdf`                                                        |        |
| 104 | `Lifetime_control/versions/v23/Lifetime control_v23.pdf`                                                        |        |
| 105 | `Lifetime_control/versions/v24/Lifetime control_v24.pdf`                                                        |        |
| 106 | `Lifetime_control/versions/v25/Gaudreau_graphene.pdf`                                                           |        |
| 107 | `Lifetime_control/versions/v25/Lifetime-control_v25.pdf`                                                        | Y      |
| 108 | `Lifetime_control/versions/v4/Lifetime control_v4.pdf`                                                          |        |
| 109 | `Lifetime_control/versions/v5/Lifetime control_v5.pdf`                                                          |        |
| 110 | `Lifetime_control/versions/v6/Lifetime control_v6.pdf`                                                          |        |
| 111 | `Lifetime_control/versions/v7/Lifetime control_v7.pdf`                                                          |        |
| 112 | `Lifetime_control/versions/v8/Lifetime control_v8.pdf`                                                          |        |
| 113 | `Lifetime_control/versions/v9/Lifetime control_v9.pdf`                                                          |        |
| 114 | `MidIRphotocurrent/MIDIR_pc_v10 copy 2.pdf`                                                                     |        |
| 115 | `MidIRphotocurrent/MIDIR_pc_v1_Frank.pdf`                                                                       |        |
| 116 | `MidIRphotocurrent/MIDIR_pc_v2.pdf`                                                                             |        |
| 117 | `MidIRphotocurrent/MIDIR_pc_v7-arxiv.pdf`                                                                       |        |
| 118 | `MidIRphotocurrent/MIDIR_pc_v7.pdf`                                                                             |        |
| 119 | `MidIRphotocurrent/proofs/proof_MB.pdf`                                                                         |        |
| 120 | `MidIRphotocurrent/resubmission/MIDIR_pc_vrev.pdf`                                                              |        |
| 121 | `MidIRphotocurrent/resubmission/MIDIR_pc_vrev_blue_FK.pdf`                                                      |        |
| 122 | `MidIRphotocurrent/v3/MIDIR_pc_v3.pdf`                                                                          |        |
| 123 | `Nanoletters_graphenestronglightmatterinteractions.../Arxiv submission/Arxiv_20110411.pdf`                      |        |
| 124 | `Nanoletters_graphenestronglightmatterinteractions.../Arxiv submission/paper.pdf`                               | Y      |
| 125 | `Nanoletters_graphenestronglightmatterinteractions.../allfiles_Javier/0953-8984_23_11_112204.pdf`               | Y      |
| 126 | `Nanoletters_graphenestronglightmatterinteractions.../allfiles_Javier/paper.pdf`                                |        |
| 127 | `Nanoletters_graphenestronglightmatterinteractions.../text/v1/graphene_dipole.pdf`                              |        |
| 128 | `Nanoletters_graphenestronglightmatterinteractions.../text/v2/paper.pdf`                                        |        |
| 129 | `Nanoletters_graphenestronglightmatterinteractions.../text/v3/Graphene_NanoPhotonics.pdf`                       |        |
| 130 | `PUBLISHED/ACSNano_Ribbon/ribbons-5.pdf`                                                                        |        |
| 131 | `PUBLISHED/ACSNano_Ribbon/ribbons.pdf`                                                                          |        |
| 132 | `PUBLISHED/NanoLetters_Quenching_graphene/ArXiv_Submitted/Lifetime-control_v25.pdf`                             |        |
| 133 | `PUBLISHED/NanoLetters_Quenching_graphene/Lifetime-control_v25.pdf`                                             |        |
| 134 | `PUBLISHED/NanoLetters_Quenching_graphene/Submission.pdf`                                                       |        |
| 135 | `PUBLISHED/NanoLetters_Quenching_graphene/Submission2/Lifetime-control_final_v0.pdf`                            |        |
| 136 | `PUBLISHED/NanoLetters_Quenching_graphene/Submission2/Lifetime-control_final_v1.pdf`                            |        |
| 137 | `PUBLISHED/NanoLetters_Quenching_graphene/Submission2/Lifetime-control_final_v2.pdf`                            |        |
| 138 | `PUBLISHED/NanoLetters_Quenching_graphene/proof2/research 1..6.pdf`                                             |        |
| 139 | `PUBLISHED/Nanoletters_graphenestronglightmatterinteractions.../allfiles_Javier/paper.pdf`                      |        |
| 140 | `PUBLISHED/Nanoletters_photodetection pn-junction graphene/pn/acs.pdf`                                          |        |
| 141 | `PUBLISHED/Nanoletters_photodetection pn-junction graphene/pn/photocurrent_36.pdf`                              |        |
| 142 | `PUBLISHED/Nanoletters_photodetection pn-junction graphene/pn/photocurrent_37.pdf`                              | Y      |
| 143 | `PUBLISHED/NatureNanotech_NV_trapping/NatPhotGeiselmann_v12.pdf`                                                | Y      |
| 144 | `PUBLISHED/NaturePhysics_CM/Paper_figures/ImpactIonizationEfficiency11.pdf`                                     | Y      |
| 145 | `PUBLISHED/NaturePhysics_CM/Preprint_CarrierMultiplicationGraphene.pdf`                                         | Y      |
| 146 | `PUBLISHED/NaturePhysics_CM/Submission1/TielrooijTextFigsSupp.pdf`                                              |        |
| 147 | `PUBLISHED/NaturePhysics_CM/Submission2/Tielrooij_CarrierMultiplicationGraphene_Main.pdf`                       |        |
| 148 | `PUBLISHED/NaturePhysics_CM/preprint/TielrooijTextFigsSupp_Arxiv.pdf`                                           |        |
| 149 | `PUBLISHED/Quenching_graphene/Lifetime control_v7.pdf`                                                          |        |
| 150 | `Photocurrent_wavelength/FemtosecondEfficientPhotodetectionGraphene.pdf`                                        |        |
| 151 | `Photocurrent_wavelength/Tielrooij_Ultrafast.pdf`                                                               |        |
| 152 | `Photocurrent_wavelength/UltrafastEfficientCarrierHeatingGraphene-1.pdf`                                        | Y      |
| 153 | `Photocurrent_wavelength/UltrafastEfficientCarrierHeatingGraphene.pdf`                                          |        |
| 154 | `Photocurrent_wavelength/WavDep_1 copy.pdf`                                                                     |        |
| 155 | `Photocurrent_wavelength/WavDep_31_FK.pdf`                                                                      |        |
| 156 | `Photocurrent_wavelength/WavDep_6.pdf`                                                                          |        |
| 157 | `Photocurrent_wavelength/WavDep_9_F copy.pdf`                                                                   |        |
| 158 | `Photocurrent_wavelength/WavDep_9_F.pdf`                                                                        |        |
| 159 | `Plasmondamping/Proofs/www.nature.com-licenceforms-npg-mpl-ltp.pdf copy.pdf`                                    | Y      |
| 160 | `THz_photodetection/Modification_of_the_paper_Draft/acs-THz_PTE_photodetector_V14.pdf`                          | Y      |
| 161 | `Ultrafast WSe2/Nature Nanotechnology _ round 3/LetterToEditor_round3.pdf`                                      |        |
| 162 | `Ultrafast WSe2/Time resolved Wse2/1503.01682v1.pdf`                                                            |        |
| 163 | `Ultrafast WSe2/Time resolved Wse2/EMRS_GSA_Massicotte.pdf`                                                     |        |
| 164 | `Ultrafast WSe2/Time resolved Wse2/EMRS_GSA_Massicotte_all.pdf`                                                 |        |
| 165 | `Ultrafast WSe2/Time resolved Wse2/EMRS_GSA_WorkDescription_Massicotte.pdf`                                     |        |

*(Note: 315 total — remaining ~150 entries are additional versions of the same papers above, bib-file references, and LaTeX package PDFs. Full list at `/tmp/suspected_papers.txt` on DGX.)*

---

## Theses & Reports (112 files)

| #   | File                                                                                                                                         | Paper? |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 1   | `Master/Master_Thesis_Achim/LaTeX/thesis.pdf`                                                                                                |        |
| 2   | `Master/Master_Thesis_Achim/Thesis_Achim.pdf`                                                                                                | Y      |
| 3   | `Master/Master_Thesis_Alvaro/Master_Thesis_Report.pdf`                                                                                       | Y      |
| 4   | `Master/Master_Thesis_Avinash/Avinash_K_Master_Thesis.pdf`                                                                                   | Y      |
| 5   | `Master/Master_Thesis_David/MasterThesis_David_Alcaraz.pdf`                                                                                  | Y      |
| 6   | `Master/Master_Thesis_Kevin/MasterThesis/Papers/Deflection and Resonators/circular_plate_deflection.pdf`                                     | Y      |
| 7   | `Master/Master_Thesis_Kevin/MasterThesis/Papers/Deflection and Resonators/ribbon_square_resonators_mc_euen.pdf`                              | Y      |
| 8   | `Master/Master_Thesis_Kevin/MasterThesis/Papers/Drum Structure Fabrication/2011BartonHigh...Resonators-1.pdf`                                | Y      |
| 9   | `Master/Master_Thesis_Kevin/MasterThesis/Papers/Drum Structure Fabrication/Graphene_Oxide_Film_Drums.pdf`                                    | Y      |
| 10  | `Master/Master_Thesis_Kevin/MasterThesis/Papers/Ferrari_raman_graphene.pdf`                                                                  | Y      |
| 11  | `Master/Master_Thesis_Kevin/MasterThesis/Papers/QD Layer and Capping/Choi_ExcitonDissociationQDs.pdf`                                        | Y      |
| 12  | `Master/Master_Thesis_Kevin/MasterThesis/Papers/QD Layer and Capping/Peterson_SinglePbS_QD_PL.pdf`                                           | Y      |
| 13  | `Master/Master_Thesis_Kevin/MasterThesis/Papers/impermeable_graphene_membranes.pdf`                                                          | Y      |
| 14  | `Master/Master_Thesis_Kevin/MasterThesis/Thesis_final.pdf`                                                                                   |        |
| 15  | `Master/Master_Thesis_Kevin/MasterThesis/master_thesis_20120828_v4.pdf`                                                                      | Y      |
| 16  | `Master/Master_Thesis_Kevin/MasterThesis/thesis_schaedler_final.pdf`                                                                         |        |
| 17  | `Master/Master_Thesis_Lorenzo/Master_Thesis_Lorenzo.pdf`                                                                                     | Y      |
| 18  | `Master/Master_Thesis_Peter/master_thesis.pdf`                                                                                               | Y      |
| 19  | `Master/Thesis Diana/Thesis Diana .pdf`                                                                                                      | Y      |
| 20  | `PhD/Geng Li_data transfer_ICFO/FTIR_Attocube.../Optical properties of CVD diamond.pdf`                                                      | Y      |
| 21  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/Proposal_Geng.pdf`                                                                           |        |
| 22  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/related paper/Dima/Dima. Quantum critical behavior...graphene.pdf`                           | Y      |
| 23  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/related paper/Feng Wang/Feng Wang. Logarithm Diameter Scaling...Plasmon.pdf`                 | Y      |
| 24  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/related paper/Feng Wang/Feng Wang. Metallic Carbon Nanotube...Resonators.pdf`                | Y      |
| 25  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/related paper/Feng Wang/Feng Wang. Nano-photocurrent Mapping...Graphene.pdf`                 | Y      |
| 26  | `PhD/Geng Li_data transfer_ICFO/Thesis proposal/related paper/Theory/Dima. Terahertz Photogalvanics...angle.pdf`                             | Y      |
| 27  | `PhD/Geng Li_data transfer_ICFO/Thesis writting/comments/Chapters5-6-proofed.pdf`                                                            |        |
| 28  | `PhD/Geng Li_data transfer_ICFO/Thesis writting/comments/Geng Li_thesis_v2_correc.pdf`                                                       |        |
| 29  | `PhD/Geng Li_data transfer_ICFO/Thesis writting/comments/Geng Li_thesis_v3_FK.pdf`                                                           |        |
| 30  | `PhD/Geng Li_data transfer_ICFO/Thesis writting/comments/Geng Li_thesis_v5_FK.pdf`                                                           |        |
| 31  | `PhD/Geng Li_data transfer_ICFO/Thesis writting/comments/Geng Li_thesis_v6_before paperpal.pdf`                                              |        |
| 32  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Manuscript_nanoletter/FTIR.pdf`                                                   |        |
| 33  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Manuscript_nanoletter/final/main text.pdf`                                        |        |
| 34  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Bernal bilayer/The electronic properties of bilayer graphene.pdf` |        |
| 35  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Dmitri K. Efetov/Dima. Quantum critical behavior...graphene.pdf`  |        |
| 36  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Feng Wang/Feng Wang. Logarithm Diameter Scaling...Plasmon.pdf`    |        |
| 37  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Francisco Guinea/Paco. Electrostatic interactions...graphene.pdf` |        |
| 38  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Hatree fock/Hartree theory calculations...graphene.pdf`           |        |
| 39  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Theory/Moiré Flat Bands...Graphene.pdf`                           |        |
| 40  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Theory/Optical conductivity...bilayers.pdf`                       |        |
| 41  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter3_paper/Refrence papers/Theory/Quasi-Flat Plasmonic Bands...Graphene.pdf`                 |        |
| 42  | `PhD/Geng Li_data transfer_ICFO/Thesis_data/Chapter4/.../paper/sboa122.pdf`                                                                  |        |
| 43  | `PhD/Krystian/Thesis/01 main.pdf`                                                                                                            |        |
| 44  | `PhD/Krystian/Thesis/01 main_2.pdf`                                                                                                          |        |
| 45  | `PhD/Krystian/Thesis/Krystian Thesis.pdf`                                                                                                    |        |
| 46  | `PhD/Krystian/Thesis/Krystian Thesis_v2.pdf`                                                                                                 |        |
| 47  | `PhD/Krystian/Thesis/Thesis.pdf`                                                                                                             | Y      |
| 48  | `PhD/Krystian/Thesis/paper stuff/Single photon paper_20231221.pdf`                                                                           |        |
| 49  | `PhD/Krystian/backup 23.08/01 main.pdf`                                                                                                      |        |
| 50  | `PhD/Krystian/backup 23.08/Krystian Thesis.pdf`                                                                                              |        |
| 51  | `PhD/Krystian/backup 23.08/Krystian_thesis.pdf`                                                                                              |        |
| 52  | `PhD/Krystian/backup 23.08/Thesis Krystian.pdf`                                                                                              | Y      |
| 53  | `PhD/Krystian/backup 23.08/paper stuff/Single photon paper_20231221.pdf`                                                                     |        |
| 54  | `PhD/Samy/Licence/Figure_12_Raman_Graphene.pdf`                                                                                              |        |
| 55  | `PhD/Samy/Licence/Figure_5a_hBn_structure.pdf`                                                                                               |        |
| 56  | `PhD/Sebastian/dissertation_Sebastian.pdf`                                                                                                   | Y      |

*(Note: 112 total — remaining ~56 entries are duplicate thesis versions and additional reference papers. Full list at `/tmp/suspected_papers_theses.txt` on DGX.)*

---

## Papers & Books (W6) — 66 files

| #   | File                                                                                                                                                           | Paper? |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 1   | `2010 -vandersypen Wedging transfer.pdf`                                                                                                                       | Y      |
| 2   | `CMOS_Circuit_Design_EN/2006_Hwang.pdf`                                                                                                                        | Y      |
| 3   | `CMOS_Circuit_Design_EN/2011_Radulov.pdf`                                                                                                                      | Y      |
| 4   | `CMOS_Circuit_Design_EN/2013_Razavi-1.pdf`                                                                                                                     | Y      |
| 5   | `CMOS_Circuit_Design_EN/2013_Wilson.pdf`                                                                                                                       | Y      |
| 6   | `Graphene School/Fuchs/JNFuchsCargese2010Graphene3_reduit.pdf`                                                                                                 | Y      |
| 7   | `Graphene noise/Low-Frequency Noise in Graphene Tunnel junhction 2018.pdf`                                                                                     | Y      |
| 8   | `Graphene noise/Noise in Graphene Superlattices Grown on hBN.pdf`                                                                                              | Y      |
| 9   | `Graphene noise/Tunability of 1_f noise at multiple Dirac cones in hBN encapsulated Gr devices.pdf`                                                            | Y      |
| 10  | `Graphene_plasmons/2006WunschDynamical polarization of graphene at finite doping.pdf`                                                                          | Y      |
| 11  | `Graphene_plasmons/2007MikhailovNon-linear electromagnetic response of graphene.pdf`                                                                           | Y      |
| 12  | `Graphene_plasmons/2008MikhailovElectromagnetic response of electrons in graphene Non-linear effects.pdf`                                                      | Y      |
| 13  | `Graphene_plasmons/2008PyatkovskiyPolarization function and plasmons in graphene with a finite gap in the quasiparticle spectrum.pdf`                          | Y      |
| 14  | `Graphene_plasmons/2008RanaGraphene Terahertz Plasmon Oscillators.pdf`                                                                                         | Y      |
| 15  | `Graphene_plasmons/2009HillDielectric function and plasmons in graphene.pdf`                                                                                   | Y      |
| 16  | `Graphene_plasmons/2010KarasawaObservation of Amplified Stimulated Terahertz Emission from Optically Pumped Heteroepitaxial Graphene-on-Silicon Materials.pdf` | Y      |
| 17  | `Graphene_plasmons/2010ShafranEnergy Transfer from an Individual Quantum Dot to a Carbon Nanotube-2.pdf`                                                       | Y      |
| 18  | `Graphene_plasmons/2011JablanTransverse electric plasmons in bilayer graphene-2.pdf`                                                                           | Y      |
| 19  | `Graphene_plasmons/2012EmaniElectrically Tunable Damping of Plasmonic Resonances with Graphene.pdf`                                                            | Y      |
| 20  | `Graphene_plasmons/2012FurchiMicrocavity-Integrated Graphene Photodetector.pdf`                                                                                | Y      |
| 21  | `Graphene_plasmons/2012Gomez-Santos 2012 Stauber - Graphene plasmons and retardation - strong light-matter coupling - 1204.6209v1.pdf`                         | Y      |
| 22  | `Graphene_plasmons/2012Gómez-SantosGraphene plasmons and retardation strong light-matter coupling.pdf`                                                         | Y      |
| 23  | `Graphene_plasmons/2012Interaction between graphene and metamaterials split rings vs. wire pairs.pdf`                                                          | Y      |
| 24  | `Graphene_plasmons/2012LlatserGraphene-based nano-patch antenna for terahertz radiation.pdf`                                                                   | Y      |
| 25  | `Graphene_plasmons/2012PeresLight scattering by a medium with a spatially modulated optical conductivity the case of graphene.pdf`                             | Y      |
| 26  | `Graphene_plasmons/2012Plasmonics of coupled graphene micro-structures.pdf`                                                                                    | Y      |
| 27  | `Graphene_plasmons/2012TR81991APlasmonic coupling in graphene micro-structures.pdf`                                                                            | Y      |
| 28  | `Graphene_plasmons/2012TselevNear-field microwave scanning probe imaging of conductivity inhomogeneities in CVD graphene-1.pdf`                                | Y      |
| 29  | `Graphene_plasmons/2012WangPlasmons and optical excitations in graphene rings.pdf`                                                                             | Y      |
| 30  | `Graphene_plasmons/2012YanInfrared Spectroscopy of Tunable Dirac Terahertz Magneto-Plasmons in Graphene.pdf`                                                   | Y      |
| 31  | `Graphene_plasmons/2012ZhouOptics InfoBase Optics Express - Interaction between graphene and metamaterials split rings vs. wire pairs.pdf`                     | Y      |
| 32  | `Handbook of graphene science/Atomic Scale Exfoliation and Adhesion of Nanocarbon.pdf`                                                                         | Y      |
| 33  | `Handbook of graphene science/Electrophoretic Deposition of Graphene Based Materials and Their Energy Related Applications.pdf`                                | Y      |
| 34  | `Handbook of graphene science/Fabrication and Applications of Biocompatible Graphene Oxide and Graphene.pdf`                                                   | Y      |
| 35  | `Handbook of graphene science/Fabrication and Characterization of Graphene and Graphene Metal Oxide Nanocomposites.pdf`                                        | Y      |
| 36  | `Handbook of graphene science/Fabrication of High Surface Area Graphene Based Nanocomposites via a Facile Chemical Route.pdf`                                  | Y      |
| 37  | `Handbook of graphene science/Formation of Graphene Layers by High Temperature Sublimation of Silicon Carbide in Vacuum.pdf`                                   | Y      |
| 38  | `Handbook of graphene science/Graphene Based Field Emission Devices.pdf`                                                                                       | Y      |
| 39  | `Handbook of graphene science/Graphene Chemiresistors as pH Sensors Fabrication and Characterization.pdf`                                                      | Y      |
| 40  | `Handbook of graphene science/Graphene Grown with PlasmaEnhanced Process and Its Applications in Lithium Ion Batteries.pdf`                                    | Y      |
| 41  | `Handbook of graphene science/Graphene Nanoribbons Synthesis by Gamma Irradiation of Graphene and Unzipping of Multiwall Carbon Nanotubes.pdf`                 | Y      |
| 42  | `Handbook of graphene science/Graphene Polymer Nanocomposites Preparation Characterization and Applications.pdf`                                               | Y      |
| 43  | `Handbook of graphene science/Graphene TiO2 Nanocomposites Synthesis Routes Characterization and Photocatalytic Performance.pdf`                               | Y      |
| 44  | `Handbook of graphene science/High Quality Graphene Sheets from Graphene Oxide Hot Pressing and Its Applications.pdf`                                          | Y      |
| 45  | `Handbook of graphene science/Hydrogenated Graphene Preparation Properties and Applications(2).pdf`                                                            |        |
| 46  | `Handbook of graphene science/Hydrogenated Graphene Preparation Properties and Applications.pdf`                                                               | Y      |
| 47  | `Handbook of graphene science/Key Points for Transferring Graphene Grown by Chemical Vapor Deposition.pdf`                                                     | Y      |
| 48  | `Handbook of graphene science/Large Scale Fabrication of High Quality Graphene Layers by Graphite Intercalation.pdf`                                           | Y      |
| 49  | `Handbook of graphene science/Mechanical Cleavage of Graphite to Graphene via Graphite Intercalation Compounds.pdf`                                            | Y      |
| 50  | `Handbook of graphene science/Preparation of Electrically Conductive Graphene Based Aerogels to Modify the Supercapacitor Electrode Surface.pdf`               | Y      |
| 51  | `Handbook of graphene science/Preparation of Graphene Oxide and Its Metal Composite Materials as Catalysts for Organic Reactions.pdf`                          | Y      |
| 52  | `Handbook of graphene science/Synthesis Methods for Graphene.pdf`                                                                                              | Y      |
| 53  | `Handbook of graphene science/Synthesis Strategies for Graphene.pdf`                                                                                           | Y      |
| 54  | `Handbook of graphene science/Synthesis and Application of Graphene Nanoribbons.pdf`                                                                           | Y      |
| 55  | `Handbook of graphene science/Synthesis of Graphene and N Doped Graphene from Flames.pdf`                                                                      | Y      |
| 56  | `Handbook of graphene science/Synthesis of Graphene by Pyrolysis of Organic Matter.pdf`                                                                        | Y      |
| 57  | `Handbook of graphene science/Synthesis of Reduced Graphene Oxide Obtained from Multiwalled Carbon Nanotubes and Its Electrocatalytic Properties.pdf`          | Y      |
| 58  | `Handbook of graphene science/Wafer Scale Chemical Vapor Deposition of High Quality Graphene on Evaporated Cu Film.pdf`                                        | Y      |
| 59  | `Inter Subband Transitions/Terahertz quantum cascade lasers.pdf`                                                                                               | Y      |
| 60  | `Journal club/Controlled modification of erbium lifetime by near field coupling to metallic films (NewJPhysics).pdf`                                           | Y      |
| 61  | `Journal club/Jones2012.pdf`                                                                                                                                   | Y      |
| 62  | `Journal club/Read/Bao et al. - 2012 - In Situ Observation of Electrostatic and Thermal Manipulation of Suspended Graphene Membranes.pdf`                      | Y      |
| 63  | `Journal club/Read/Wu et al. - 2012 - Hot Phonon Dynamics in Graphene.pdf`                                                                                     | Y      |
| 64  | `Journal club/Unread/Bissett et al. - 2012 - Effect of Domain Boundaries on the Raman Spectra of Mechanically Strained Graphene.pdf`                           | Y      |
| 65  | `Journal club/Unread/Perruisseau-Carrier - 2012 - Graphene for Antenna Applications Opportunities and Challenges from Microwaves to THz.pdf`                   | Y      |
| 66  | `Romain/BrarVW_AtwaterHA_Highly confined Tunable Mid-Infrared Plasmonics in Graphene Nanoresonators_NanoLett_2013.pdf`                                         | Y      |

*(Full list at `/tmp/suspected_papers_books.txt` on DGX.)*

---

## Projects (W10) — ⚠️ Scan blocked (CIFS timeout)

`find` on `/ICFO/groups/NOE/Projects` timed out after 300s — same CIFS hang as the Notebook folder. Cannot generate paper list until the mount is more stable or we split by subfolder. See `SERVER_INGESTION_ISSUES.md` for options.

---

## Notes

- Many W2 entries are **multiple versions of the same paper** (v1–v25 of "Lifetime control", "MIDIR_pc", etc.) — you likely only need to Docling the final version
- W12 entries include actual **thesis PDFs** (YES for Docling) and **reference papers inside thesis folders** (also YES)
- Some entries are **LaTeX package PDFs** (`achemso-demo.pdf`, `natmove-manual.pdf`) — these are NOT papers, mark NO
- **Licence forms** (`www.nature.com-licenceforms...`) — mark NO
