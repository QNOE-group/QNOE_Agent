# Provence vs Cross-Encoder — qnoe_rag reranker eval

*Date: 2026-07-09 · agent venv · vLLM not required · Provence threshold=0.1*
*Provence: naver/provence-reranker-debertav3-v1 @ ef49e233 · CE: cross-encoder-msmarco · pool=20, top_k=3*

## Summary

- Queries: 20  (pools non-empty: 20)
- Mean top-3 tokens: **cross-encoder 1631 → Provence 454**  (**72% reduction**)
- Answer-keyword survival: cross-encoder 20/20 · **Provence 20/20**
- CE top-1 source retained in Provence top-3: 17/20
- Mean rerank latency (cpu): cross-encoder 673 ms → Provence 21881 ms  (**32.51× CE**)

### Gate check
- [PASS] Provence keeps answer-bearing content in >=18/20  → 20/20
- [PASS] Mean top-3 token count drops >=35%  → 72%
- [FAIL] CPU latency <= ~2x cross-encoder  → 32.51x

## Per-query

| # | query | pool | CE tok | Prov tok | reduc% | CE kw | Prov kw | src-agree |
|---|---|---|---|---|---|---|---|---|
| 1 | How does the quantum twisting microscope measure | 20 | 927 | 171 | 82 | Y | Y | Y |
| 2 | What is the magic angle in twisted bilayer graph | 20 | 9866 | 2513 | 75 | Y | Y | Y |
| 3 | How is the tip approach and piezo positioning co | 20 | 992 | 599 | 40 | Y | Y | Y |
| 4 | What determines the tunneling current between th | 20 | 1587 | 342 | 78 | Y | Y | Y |
| 5 | How do we calibrate the twist angle in situ duri | 20 | 735 | 275 | 63 | Y | Y | Y |
| 6 | Explain the photocurrent measurement technique f | 20 | 1078 | 471 | 56 | Y | Y | n |
| 7 | What is the role of the gate voltage in scanning | 20 | 821 | 252 | 69 | Y | Y | n |
| 8 | How is the photothermoelectric effect distinguis | 20 | 939 | 285 | 70 | Y | Y | Y |
| 9 | What laser wavelengths are used in the photocurr | 20 | 631 | 87 | 86 | Y | Y | Y |
| 10 | How do we extract carrier density and mobility f | 20 | 1201 | 94 | 92 | Y | Y | Y |
| 11 | What QCoDeS parameters are recorded in a magneto | 20 | 167 | 402 | -141 | Y | Y | Y |
| 12 | Show measurements of longitudinal resistance Rxx | 20 | 733 | 166 | 77 | Y | Y | Y |
| 13 | Find runs measuring Hall resistance Rxy as a fun | 20 | 999 | 487 | 51 | Y | Y | Y |
| 14 | What is the typical base temperature in the dilu | 20 | 4488 | 446 | 90 | Y | Y | Y |
| 15 | Explain polariton condensation in a 2D semicondu | 20 | 1267 | 147 | 88 | Y | Y | Y |
| 16 | What is the Hopfield coefficient and its role in | 20 | 699 | 93 | 87 | Y | Y | Y |
| 17 | How does hBN encapsulation improve graphene devi | 20 | 1039 | 374 | 64 | Y | Y | Y |
| 18 | What signatures indicate the quantum Hall effect | 20 | 1322 | 607 | 54 | Y | Y | Y |
| 19 | Describe the git branching and pull request work | 13 | 1372 | 821 | 40 | Y | Y | Y |
| 20 | What superconducting materials are studied and h | 20 | 1763 | 453 | 74 | Y | Y | n |

## Raw top-3 (for manual answer-bearing judgment)


### Q1: How does the quantum twisting microscope measure the electronic band structure?
*expected keywords: ['twist', 'momentum', 'tunnel'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97E42594-8BE0-4530-80D9-D7C98CFA0386%7D&file=MSc%20Thesis%20Proposal_QTOM_2025_26.docx&action=default&mobileredirect=true` (297 tok): .Batlle@icfo.eu
Phone number: 935534163
Mail address: Mediterranean Technology Park, Avinguda Carl Friedrich Gauss, 3, 08860 Castelldefels, Barcelona
Keywords:
Summary of the subject (maximum 1 page):
The quantum twisting microscope (QTM) is an emerging scanning probe platform th...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B3204E0C3-5C42-4C40-9591-C9C70A9F6263%7D&file=Main%20Text%2027-7-2023.docx&action=default&mobileredirect=true` (315 tok): ticle band structure (see detailed discussions below), we calculate the optical conductivity (Fig. 2c) and identify the inter-band transitions responsible for the observed spectral features (Fig. 2d).
Having identified mid-infrared fingerprints unique to twisted bilayer graphene,...
- [3] `/ICFO/groups/NOE/Projects/TBG_FTIR/Final_everything/Writing. Latex/Jul 19, 2023/Roshan Jul27/Main Text 27-7-2023 Geng.docx` (315 tok): ticle band structure (see detailed discussions below), we calculate the optical conductivity (Fig. 2c) and identify the inter-band transitions responsible for the observed spectral features (Fig. 2d).
Having identified mid-infrared fingerprints unique to twisted bilayer graphene,...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97E42594-8BE0-4530-80D9-D7C98CFA0386%7D&file=MSc%20Thesis%20Proposal_QTOM_2025_26.docx&action=default&mobileredirect=true` (87 tok): Unlike conventional STM, where tunnelling occurs locally and primarily probes the real-space density of states, the QTM can access momentum-resolved information through the moiré-induced momentum mixing between tip and sample states. In this way, the QTM bridges real-space imagin...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B08361902-8487-4925-97FB-342CC9941BD3%7D&file=maintext_v8_JB.docx&action=default&mobileredirect=true` (42 tok): The same applies to the recent Quantum Twisting Microscope [30], which resolves band structure through momentum-resolved tunnelling, but it involves complex fabrication that is not readily accessible in most condensed matter labs....
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BD8A9AF43-6A87-48D5-9FAE-6B09D079815F%7D&file=Maintext_v9.docx&action=default&mobileredirect=true` (42 tok): The same applies to the recent Quantum Twisting Microscope [30], which resolves band structure through momentum-resolved tunnelling, but it involves complex fabrication that is not readily accessible in most condensed matter labs....

### Q2: What is the magic angle in twisted bilayer graphene and why do flat bands appear?
*expected keywords: ['magic', 'angle', 'flat band'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Projects/TBG_FTIR/Project. PhD. TBG_FTIR/Project. PhD. TBG_FTIR/reference paper/Theory/* Origin of Magic Angles in Twisted Bilayer Graphene.pdf` (9254 tok): Origin of Magic Angles in Twisted Bilayer Graphene
Grigory Tarnopolsky, Alex Jura Kruchkov, * and Ashvin Vishwanath
Department of Physics, Harvard University, Cambridge, Massachusetts 02138, USA
(Received 24 November 2018; published 15 March 2019)
Twisted bilayer graphene (TBG) w...
- [2] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/Thesis/Ch_1_2.docx` (306 tok): Brillouin zones of two graphene single layers (red and blue) rotated by angle θ span a pair of superlattice mini-Brillouin zones of twisted bilayer graphene (black). Copied from 19.
2D moiré materials
Shortly before the breakthrough experimental papers on graphene/hBN superlattic...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/backup 23.08/Ch_1_2.docx` (306 tok): Brillouin zones of two graphene single layers (red and blue) rotated by angle θ span a pair of superlattice mini-Brillouin zones of twisted bilayer graphene (black). Copied from 19.
2D moiré materials
Shortly before the breakthrough experimental papers on graphene/hBN superlattic...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Projects/TBG_FTIR/Project. PhD. TBG_FTIR/Project. PhD. TBG_FTIR/reference paper/Theory/* Origin of Magic Angles in Twisted Bilayer Graphene.pdf` (2374 tok): Importantly, these phenomena are observed in a narrow range of twist angles near 1.05°, i.e., the first magic angle where the isolated and relatively flat band appear near neutrality [29–33]. To date, the origin and recurrence of the magic angles is not clear, even whether it is...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BF4541F0C-28C3-4DE9-9CB9-AF712A0C20DD%7D&file=Flat%20bands%20in%20the%20Flatlands%20%E2%80%93%20opto-electronic%20adventures_Friday13th_version.pptx&action=edit&mobileredirect=true` (74 tok): [Slide 5] Magic angle twisted bilayer graphene (MATBG) https://www.quantamagazine.org/how-twisted-graphene-became-the-big-thing-in-physics-20190430/ At around 1.1o magic happens The bands at Fermi level become flat (very low dispersion). Courtesy of dr Iacopo Torre....
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/Thesis/Ch_1_2.docx` (65 tok): A set of special twist angles, dubbed ’Magic Angles’, was identified, at which the bands at the Fermi level become almost dispersionless or ’flat’. Flat bands are interesting, because the electrons living is a flat band have a very large mass and are well localized in space, ofte...

### Q3: How is the tip approach and piezo positioning controlled in the QTM setup?
*expected keywords: ['piezo', 'tip', 'approach'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/opt/qnoe-agent/repos/QTM-CodeBase/README.md` (459 tok): # QTM Experiment — Measurement Codebase

Automated electrical transport measurement suite for a **Quantum Twisting Microscope (QTM)**: a scanning probe instrument with a piezo-driven sample rotator, enabling controlled angular alignment between a conductive tip and a 2D material...
- [2] `/ICFO/groups/NOE/Lab_Instruments/Thorlabs Stage - RotationMount/APT/Manuals/Motion Control/HA0248T_BPC301_Benchtop Piezo Controller.pdf` (266 tok): ogress and the displayed position counts down
towards zero (but may not reach zero).
2) When the zeroing move has been completed, the ‘Zero’ LED is lit and the
controller switches to closed loop mode.

24 HA0248T Rev B Nov 2012 
Chapter 4
4.4 Moving the Piezo
The piezo can be man...
- [3] `/ICFO/groups/NOE/Lab_Instruments/Thorlabs Stage - RotationMount/APT/Manuals/Motion Control/HA0137T_BPC201_Piezo Controller.pdf` (267 tok): button flashes
to indicate that zeroing is in progress and the displayed position counts down
towards zero (but may not reach zero).
2) When the zeroing move has been completed, the ‘Zero’ LED is lit.

24 HA0137T Rev 8 June 2011 
Chapter 4
4.4 Moving the Piezo
The piezo can be ma...

**Provence top-3 (pruned):**
- [1] `/opt/qnoe-agent/repos/QTM-CodeBase/README.md` (143 tok): --- ## What this repo does - Connects to and controls the **Zurich Instruments MFLI** lock-in amplifier (bias, gate, AC excitation, demodulation, scope) - Drives the **Attocube ANC350** piezo rotator to set the twist angle between tip and sample - Records **electrical transport d...
- [2] `/ICFO/groups/NOE/Personal/Sergi/QTM - Copy/Attocube controller/Attocube/Application Notes/AppNote P16 - ANPz100 - Break Junctions.pdf` (228 tok): After fabrication, samples were placed onto the breaking mechanism, consisting of a chip carrier, a micrometer screw-controlled x-y table and an attocube ANPz100 positioner, see Figure 1. The ANPz100 was used in slip- stick mode for coarse approach, and in scanning mode to adjust...
- [3] `/ICFO/groups/NOE/Lab_Instruments/Attocube CD/Application Notes/AppNote P16 - ANPz100 - Break Junctions.pdf` (228 tok): After fabrication, samples were placed onto the breaking mechanism, consisting of a chip carrier, a micrometer screw-controlled x-y table and an attocube ANPz100 positioner, see Figure 1. The ANPz100 was used in slip- stick mode for coarse approach, and in scanning mode to adjust...

### Q4: What determines the tunneling current between the two graphene layers in the QTM?
*expected keywords: ['tunnel', 'current', 'overlap'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/Shared%20Documents/QTOM/Relevant%20papers/plasmon-generation-through-electron-tunneling-in-graphene.pdf` (592 tok): l scale). We consider a graphene spacing d = 1 nm, Fermi energies E F1 = 1 eV and E F2 = 0.5 eV, and a bias eV b = 1.2 eV in all cases. The graphene conductivity is modeled in the RPA.

<!-- image -->

The elements involved in the theoretical description of inelastic electron tun...
- [2] `/ICFO/groups/NOE/Meetings/JC Presentations/20180404_DavidA/paper295.pdf` (592 tok): l scale). We consider a graphene spacing d = 1 nm, Fermi energies E F1 = 1 eV and E F2 = 0.5 eV, and a bias eV b = 1.2 eV in all cases. The graphene conductivity is modeled in the RPA.

<!-- image -->

The elements involved in the theoretical description of inelastic electron tun...
- [3] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/Shared%20Documents/QTOM/Relevant%20papers/plasmon-generation-through-electron-tunneling-in-graphene.pdf` (403 tok): structure provides a key element for future optics-free integrated devices and could also be operated in reversed mode to detect plasmons by decay into tunneled electrons.

## ■ RESULTS AND DISCUSSION

Plasmon Generation through Electron Tunneling. The structure under considerati...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/Shared%20Documents/QTOM/Relevant%20papers/plasmon-generation-through-electron-tunneling-in-graphene.pdf` (125 tok): The inelastic tunneling current density is then expressed as an integral over parallel electron wave-vectors (see eq 2), which involves the Fermi -Dirac occupation distributions of the graphene bands in the two layers (we assume a temperature of 300 K). The screened Coulomb inter...
- [2] `/ICFO/groups/NOE/Meetings/JC Presentations/20180404_DavidA/paper295.pdf` (125 tok): The inelastic tunneling current density is then expressed as an integral over parallel electron wave-vectors (see eq 2), which involves the Fermi -Dirac occupation distributions of the graphene bands in the two layers (we assume a temperature of 300 K). The screened Coulomb inter...
- [3] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/Shared%20Documents/QTOM/Relevant%20papers/plasmon-generation-through-electron-tunneling-in-graphene.pdf` (92 tok): Upon application of a bias voltage V b between the two carbon layers, electrons can tunnel from one to the other, assisted by the excitation of a propagating plasmon (inelastic tunneling). The graphene layers are described through their wave-vectorand frequency-dependent conducti...

### Q5: How do we calibrate the twist angle in situ during a QTM measurement?
*expected keywords: ['twist', 'angle', 'calibrat'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/_layouts/15/Doc.aspx?sourcedoc=%7BC797A6F4-9566-445A-8BAC-80E33BF38FDC%7D&file=THz%20QTM%20documentation%20v3.docx&action=default&mobileredirect=true` (225 tok): l (copied from Geng’s setup, see picture below).
FTIR_step_scan_readmirror()
Data comes out vs distance. Open a notebook for data analysis. Typically, Likun uses two, one for QTM and another for FTIR.
Twist_measure.py for measurement of FTIR+twist angle. It imports the funciont f...
- [2] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/_layouts/15/Doc.aspx?sourcedoc=%7BAA6287C0-2C0A-43ED-B0F2-92B38FA4008D%7D&file=THz%20QTM%20documentation%20v3.docx&action=default&mobileredirect=true` (225 tok): l (copied from Geng’s setup, see picture below).
FTIR_step_scan_readmirror()
Data comes out vs distance. Open a notebook for data analysis. Typically, Likun uses two, one for QTM and another for FTIR.
Twist_measure.py for measurement of FTIR+twist angle. It imports the funciont f...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BCE943093-0545-4CA1-B5B6-01CDC209243C%7D&file=vdWSymposium2025_Likun%20Wang.pptx&action=edit&mobileredirect=true` (285 tok): Optical spectroscopy allows us to measure: 
Interband transitions in moire systems [2, 3];
Excitons in gapped bilayer graphene [4];
Photon assisted electron tunneling process in tunneling devices [5]. 

QTM is a new platform to measure: 
In-situ twistronics of 2D materials;
Band...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/_layouts/15/Doc.aspx?sourcedoc=%7BC797A6F4-9566-445A-8BAC-80E33BF38FDC%7D&file=THz%20QTM%20documentation%20v3.docx&action=default&mobileredirect=true` (66 tok): It imports the funciont from Twist_module.py: Twist_openloop_ftir_save() Trick: before measuring, move to desired angle +1deg. Then move -1deg. We do this to reduce the effects of backlash. When measuring, comment the movement function and the parameters freq and amp are redefine...
- [2] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/_layouts/15/Doc.aspx?sourcedoc=%7BAA6287C0-2C0A-43ED-B0F2-92B38FA4008D%7D&file=THz%20QTM%20documentation%20v3.docx&action=default&mobileredirect=true` (66 tok): It imports the funciont from Twist_module.py: Twist_openloop_ftir_save() Trick: before measuring, move to desired angle +1deg. Then move -1deg. We do this to reduce the effects of backlash. When measuring, comment the movement function and the parameters freq and amp are redefine...
- [3] `/opt/qnoe-agent/repos/QTM-CodeBase/README.md` (143 tok): --- ## What this repo does - Connects to and controls the **Zurich Instruments MFLI** lock-in amplifier (bias, gate, AC excitation, demodulation, scope) - Drives the **Attocube ANC350** piezo rotator to set the twist angle between tip and sample - Records **electrical transport d...

### Q6: Explain the photocurrent measurement technique for graphene devices.
*expected keywords: ['photocurrent', 'laser', 'gate'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Manuscripts/Dissociation Stark effect WSe2/Paper Dissociation/old/Storyline Dissociation_2.docx` (398 tok): find that electric field profile is much smaller than the photocurrent profile, indicating a significant amount of exciton are not reaching the junction
EXTREMELY BAD. Major figure/text change needed.
Structure of: Photocurrent measurements of supercollision cooling in graphene
A...
- [2] `/ICFO/groups/NOE/Manuscripts/Ultrafast WSe2/Nature Nanotechnology _ round 3/ultrafast-wse2-paper_Round3_V2F.docx` (340 tok): substrate covered with a 285 nm thick SiO2 layer, which we use as a back gate (VG). Top and bottom graphene flakes are electrically connected by one-dimensional contacts33 made of 2 nm Ti/ 100 nm Au.
Optoelectronic measurements. Photocurrent is generated by focusing a laser beam...
- [3] `/ICFO/groups/NOE/Manuscripts/Ultrafast WSe2/Response-2nd round/ultrafast-wse2-paper_VF_Nature_Nano_Rnd2_MM_FV_MM.docx` (340 tok): substrate covered with a 285 nm thick SiO2 layer, which we use as a back gate (VG). Top and bottom graphene flakes are electrically connected by one-dimensional contacts33 made of 2 nm Ti/ 100 nm Au.
Optoelectronic measurements. Photocurrent is generated by focusing a laser beam...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Manuscripts/Ultrafast WSe2/Nature Nanotechnology _ round 3/ultrafast-wse2-paper_Round3_V2F.docx` (157 tok): Optoelectronic measurements. Photocurrent is generated by focusing a laser beam (close to diffraction limit) with a microscope objective (Olympus LUCPlanFLN 40x) on the device, and measured with a preamplifier and a lock-in amplifier synchronized with a mechanical chopper. A supe...
- [2] `/ICFO/groups/NOE/Manuscripts/Ultrafast WSe2/Response-2nd round/ultrafast-wse2-paper_VF_Nature_Nano_Rnd2_MM_FV_MM.docx` (157 tok): Optoelectronic measurements. Photocurrent is generated by focusing a laser beam (close to diffraction limit) with a microscope objective (Olympus LUCPlanFLN 40x) on the device, and measured with a preamplifier and a lock-in amplifier synchronized with a mechanical chopper. A supe...
- [3] `/ICFO/groups/NOE/Manuscripts/Ultrafast WSe2/Nature Nanotechnology _ round 3/ultrafast-wse2-paper_Round3_V2.docx` (157 tok): Optoelectronic measurements. Photocurrent is generated by focusing a laser beam (close to diffraction limit) with a microscope objective (Olympus LUCPlanFLN 40x) on the device, and measured with a preamplifier and a lock-in amplifier synchronized with a mechanical chopper. A supe...

### Q7: What is the role of the gate voltage in scanning photocurrent microscopy?
*expected keywords: ['gate', 'voltage', 'photocurrent'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Theses_Reports_thesisproposal/Thesis/SebastianCastilla/dissertation_Sebastian.pdf` (200 tok): as a function of the two gates. They are controlled independently and several junction configurations are formed as indicated in the figure.

<!-- image -->

## 2.3.2. Scanning photocurrent microscopy

The technique scanning photocurrent microscopy (SPM) consists on scanning a sa...
- [2] `/ICFO/groups/NOE/Theses & reports/PhD/Sebastian/dissertation_Sebastian.pdf` (200 tok): as a function of the two gates. They are controlled independently and several junction configurations are formed as indicated in the figure.

<!-- image -->

## 2.3.2. Scanning photocurrent microscopy

The technique scanning photocurrent microscopy (SPM) consists on scanning a sa...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B203A3A3E-5485-40B6-9212-92AD7082BEE5%7D&file=ICFO_Paper_Introduction_Bandwidth_data_V2.docx&action=default&mobileredirect=true` (421 tok): hBN/Gr/hBN heterostructure. The electrical and optoelectronic properties of the photodetectors were characterized, and their mobilities, n*, and OGV were carefully extracted (see Supplementary XXXX).
Scattering-type Scanning Near-Field Optical Microscopy (SNOM) was performed on t...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Theses_Reports_thesisproposal/Thesisproposals/Sergi/Sergi_FK.pdf` (96 tok): by using conventional metallized AFM cantilevers, it becomes possible to measure the photocurrent of the sample by sweeping the gate and this can allow us to extract local twist angle variation [44]. Some challenges arise while determining the precise relationship between the gat...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B203A3A3E-5485-40B6-9212-92AD7082BEE5%7D&file=ICFO_Paper_Introduction_Bandwidth_data_V2.docx&action=default&mobileredirect=true` (78 tok): Voltages were applied to the bottom split gates ( hBN/Gr heterostructure) to create a p-n junction. Next, we performed a gate voltage-dependent linescan by scanning along the blue dotted line while simultaneously sweeping the gate voltage (left gate = right gate), that is, the p-...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BA80951F9-0C25-4E03-8D95-160DC9541BB1%7D&file=Waveguide_V1_AM.docx&action=default&mobileredirect=true` (78 tok): Voltages were applied to the bottom split gates ( hBN/Gr heterostructure) to create a p-n junction. Next, we performed a gate voltage-dependent linescan by scanning along the blue dotted line while simultaneously sweeping the gate voltage (left gate = right gate), that is, the p-...

### Q8: How is the photothermoelectric effect distinguished from the photovoltaic effect?
*expected keywords: ['photothermoelectric', 'seebeck', 'photovoltaic'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/Thesis/Ch_1_2.docx` (313 tok): ) in a process that is captured by the Shockley-Ramo- like theory 89,107. We will focus on the different physical mechanisms by which a local current/voltage source may be created.
Photovoltaic effect
The photovoltaic effect is presumably the most studied photocurrent generation...
- [2] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/backup 23.08/01 main.docx` (313 tok): ) in a process that is captured by the Shockley-Ramo- like theory 89,107. We will focus on the different physical mechanisms by which a local current/voltage source may be created.
Photovoltaic effect
The photovoltaic effect is presumably the most studied photocurrent generation...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/backup 23.08/Ch_1_2.docx` (313 tok): ) in a process that is captured by the Shockley-Ramo- like theory 89,107. We will focus on the different physical mechanisms by which a local current/voltage source may be created.
Photovoltaic effect
The photovoltaic effect is presumably the most studied photocurrent generation...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/Thesis/Ch_1_2.docx` (95 tok): As a zero- bandgap material, graphene does not so easily produce a strong in-plane field at junctions. This, combined with other properties that will be discussed in the next section, favors the photothermoelectric effect over the photovoltaic effect as the dominant mechanism for...
- [2] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/backup 23.08/01 main.docx` (95 tok): As a zero- bandgap material, graphene does not so easily produce a strong in-plane field at junctions. This, combined with other properties that will be discussed in the next section, favors the photothermoelectric effect over the photovoltaic effect as the dominant mechanism for...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Krystian/backup 23.08/Ch_1_2.docx` (95 tok): As a zero- bandgap material, graphene does not so easily produce a strong in-plane field at junctions. This, combined with other properties that will be discussed in the next section, favors the photothermoelectric effect over the photovoltaic effect as the dominant mechanism for...

### Q9: What laser wavelengths are used in the photocurrent experiments?
*expected keywords: ['wavelength', 'laser', 'nm'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Manuscripts/IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v9/MIDIR_pc_v9.pdf` (211 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10 µ m wavelength range. Device 1 is used in Figure 1, device 2 is used in Figure 2, 3 and 5 and device 3 is used in Figure 4.

The scanning photocurrent images are collected by focusing the laser beam with...
- [2] `/ICFO/groups/NOE/Manuscripts/MidIRphotocurrent/MIDIR_pc_v10 copy 2.pdf` (210 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10 µ m wavelength range. Device 1 is used in Figure 1, device 2 is used in Figure 2, 3 and 5 and device 3 is used in Figure 4.

The scanning photocurrent images are collected by focusing the laser beam with...
- [3] `/ICFO/groups/NOE/Manuscripts/IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v10/MIDIR_pc_v10.pdf` (210 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10 µ m wavelength range. Device 1 is used in Figure 1, device 2 is used in Figure 2, 3 and 5 and device 3 is used in Figure 4.

The scanning photocurrent images are collected by focusing the laser beam with...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Manuscripts/IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v9/MIDIR_pc_v9.pdf` (29 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10  m wavelength range....
- [2] `/ICFO/groups/NOE/Manuscripts/MidIRphotocurrent/MIDIR_pc_v10 copy 2.pdf` (29 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10  m wavelength range....
- [3] `/ICFO/groups/NOE/Manuscripts/IR Photodetection/MID_IRpc_dataanalysis_and_tex/tex/versions/v10/MIDIR_pc_v10.pdf` (29 tok): is 5-10 Ω / cm in order to optimize the transmission of light in the ∼ 6-10  m wavelength range....

### Q10: How do we extract carrier density and mobility from a Hall bar measurement?
*expected keywords: ['carrier density', 'mobility', 'hall'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_High_quality_heterostructure_paperpal_V3.docx` (447 tok): ed, with magnitudes of +/-0. 4 T. The sample was subjected to a bias current of 100 nA.
The carrier density can be extracted using from the hall Hall resistivity using the following formula: as below;
where B is the perpendicular magnetic field applied. where, B is the applied pe...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Theses_Reports_thesisproposal/Thesis/SebastianCastilla/dissertation_Sebastian.pdf` (377 tok): ice B.

<!-- image -->

Additionally, we fabricate a reference device with Hall bar geometry configuration by following the fabrication procedure described above. We achieve a high mobility of 100,000

Fig. 3.2.: a) Measured resistance map as a function of the right gate (left ax...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Sebastian/dissertation_Sebastian.pdf` (377 tok): ice B.

<!-- image -->

Additionally, we fabricate a reference device with Hall bar geometry configuration by following the fabrication procedure described above. We achieve a high mobility of 100,000

Fig. 3.2.: a) Measured resistance map as a function of the right gate (left ax...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_High_quality_heterostructure_paperpal_V3.docx` (40 tok): The carrier density can be extracted using from the hall Hall resistivity using the following formula: as below; where B is the perpendicular magnetic field applied. where, B is the applied perpendicular magnetic field....
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BD03CC0AF-0ECF-4D76-B9DD-4F79E4FA1563%7D&file=Samy_Thesis_Chapters_Compiled_FK2.docx&action=default&mobileredirect=true` (27 tok): The carrier density can be extracted using the hall resistivity using the formula as below; where, B is the applied perpendicular magnetic field....
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97210214-BD21-4415-901E-8B81F51F42E9%7D&file=Samy_Thesis_Chapters_Compiled_FK.docx&action=default&mobileredirect=true` (27 tok): The carrier density can be extracted using the hall resistivity using the formula as below; where, B is the applied perpendicular magnetic field....

### Q11: What QCoDeS parameters are recorded in a magnetotransport run?
*expected keywords: ['qcodes', 'parameter', 'field'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/tmp/qnoe-sharepoint-qcodes/noe-group/General/Projects/Cavity QED/P4 - SLG devices/SLG04/SpecMag/databases/SLG04.db` (92 tok): QCoDeS measurement run
Experiment: magnetotransport_characterization
Sample: SLG04
Run 26: Magnetotransport_map_30uV_dark
Completed: 1726527121.114053
Parameters: mips_field, keithley_smua_volt, keithley_smua_curr, lockin_SR1_complex_voltage, mips_temp, mitc_vti_temp
Database: SL...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Projects/Cavity%20QED/P4%20-%20SLG%20devices/SLG04/SpecMag/meas%20files/meas_notebook_SLG04.ipynb` (32 tok): exp = qcodes.load_or_create_experiment(
    experiment_name='magnetotransport_check_Nov24',
    sample_name='SLG04'
)...
- [3] `/tmp/qnoe-sharepoint-qcodes/noe-group/General/Projects/Heavy Fermion TSTG/tTLc03/Spectramag/Sergi/spectramag.db` (43 tok): QCoDeS measurement run
Experiment: spectramag
Sample: tTLc03
Run 80: hysteresis
Completed: unknown
Parameters: unknown
Database: spectramag.db...

**Provence top-3 (pruned):**
- [1] `/tmp/qnoe-sharepoint-qcodes/noe-group/General/Projects/Cavity QED/P4 - SLG devices/SLG04/SpecMag/databases/SLG04.db` (86 tok): QCoDeS measurement run Experiment: magnetotransport_characterization Sample: SLG04 Run 26: Magnetotransport_map_30uV_dark Completed: 1726527121.114053 Parameters: mips_field, keithley_smua_volt, keithley_smua_curr, lockin_SR1_complex_voltage, mips_temp, mitc_vti_temp Database: SL...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Projects/Cavity%20QED/P4%20-%20SLG%20devices/SLG04/SpecMag/meas%20files/meas_notebook_SLG04.ipynb` (0 tok): ...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Setups_instruments_Manuals_Docs_etc/L208_THz%20ARS/old_drive/Databases_tests_temperature/T_tests_20250113.ipynb` (316 tok): #TIME TRACE from qcodes.parameters import ElapsedTimeParameter, Parameter #Settin the Input Resistor Parameter of the station to the value we are using: R0 = 1000000 #[Ohm] station.R0(R0) #--> NOTE: It will be recorded in the station snapshot for each measurement, # if you change...

### Q12: Show measurements of longitudinal resistance Rxx versus gate voltage.
*expected keywords: ['rxx', 'gate', 'resistance'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Projects/QDphotodetector/Literature/Graphene 2014/Graphene2014_ConferenceBook.pdf` (111 tok): Figures 
 
 
 
Figure 1:  Hall and longitudinal resistance versus 
gate voltage. Inset: Rxx  vs I. 
 
 
 
 
 
 
Figure 2: σxx  (σ xy  in inset) versus the filling factor 
υ between 0.3 K and 40 K

Graphene2014           May 06L09, 2014 Toulouse (France)          151  
 
 
Figure...
- [2] `/ICFO/groups/NOE/Notebook/TopoNanop/Patterned gates transport/DevBW2_SLG_47nm_Square/PROJECT_SUMMARY.md` (545 tok): Longitudinal resistance vs. patterned gate voltage (PBG)
- Multiple back gate voltages (BG): -70V, 0V, +70V
- Different contact pairs (C1-C2, C2-C3, C3-C1, etc.)
- Temperature dependence (5K to 100K)

### 2. **Magnetoresistance**
- Rxx vs. magnetic field (B) and gate voltage (PBG...
- [3] `/ICFO/groups/NOE/Projects/TopoNanop/David1D/Bonding Scheme.pptx` (77 tok): [Slide 8] 5 K Longitudinal resistance
If we ignore hysterysis and try to make a statement,  by plotting data always for the same sweep direction, we see qualitatively similar behaviour to Davids previous measurements for Rxx

Note all curves on the right panel are plotted for swe...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Notebook/TopoNanop/Patterned gates transport/DevBW2_SLG_47nm_Square/PROJECT_SUMMARY.md` (71 tok): Longitudinal resistance vs. patterned gate voltage (PBG) - Multiple back gate voltages (BG): -70V, 0V, +70V - Different contact pairs (C1-C2, C2-C3, C3-C1, etc.) - Temperature dependence (5K to 100K) ### 2....
- [2] `/ICFO/groups/NOE/Projects/QDphotodetector/Literature/Graphene 2014/Graphene2014_ConferenceBook.pdf` (22 tok): Figures Figure 1: Hall and longitudinal resistance versus gate voltage. Inset: Rxx vs I....
- [3] `/ICFO/groups/NOE/Projects/TopoNanop/David1D/Bonding Scheme.pptx` (73 tok): [Slide 8] 5 K Longitudinal resistance If we ignore hysterysis and try to make a statement, by plotting data always for the same sweep direction, we see qualitatively similar behaviour to Davids previous measurements for Rxx Note all curves on the right panel are plotted for sweep...

### Q13: Find runs measuring Hall resistance Rxy as a function of magnetic field.
*expected keywords: ['rxy', 'hall', 'field'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Projects/Patterned_Kagome/BW11_SLG_Kagome%20and%20Sq/02_BW11_analysis_highfield.ipynb` (181 tok): # Square lattice - Rxy vs Vbg and B (dfs[4])
# Measurement: High field map (dfs[4])
# Hall resistance Rxy measured as function of back gate voltage and magnetic field
# Lockin 4: contact 16,19 - Rxy D2 (Square)
fig, ax = plt.subplots(figsize=(3.2,3),dpi=180)

pc = ax.pcolormesh(v...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BD03CC0AF-0ECF-4D76-B9DD-4F79E4FA1563%7D&file=Samy_Thesis_Chapters_Compiled_FK2.docx&action=default&mobileredirect=true` (409 tok): obility calculated from the  and the Hall mobility  (where, ) is compared and the plot exhibits a perfect match when , validating the analysis performed using  in the previous section of this chapter.
Figure 2.5.4.5., Hall measurements of the TFSI treated Hallbar adapted and repr...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97210214-BD21-4415-901E-8B81F51F42E9%7D&file=Samy_Thesis_Chapters_Compiled_FK.docx&action=default&mobileredirect=true` (409 tok): obility calculated from the  and the Hall mobility  (where, ) is compared and the plot exhibits a perfect match when , validating the analysis performed using  in the previous section of this chapter.
Figure 2.5.4.5., Hall measurements of the TFSI treated Hallbar adapted and repr...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Projects/Patterned_Kagome/BW11_SLG_Kagome%20and%20Sq/02_BW11_analysis_highfield.ipynb` (183 tok): # Square lattice - Rxy vs Vbg and B (dfs[4]) # Measurement: High field map (dfs[4]) # Hall resistance Rxy measured as function of back gate voltage and magnetic field # Lockin 4: contact 16,19 - Rxy D2 (Square) fig, ax = plt.subplots(figsize=(3.2,3),dpi=180) pc = ax.pcolormesh(vb...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BD03CC0AF-0ECF-4D76-B9DD-4F79E4FA1563%7D&file=Samy_Thesis_Chapters_Compiled_FK2.docx&action=default&mobileredirect=true` (152 tok): In Figure 2.5.4.6.a., the Landau fan diagram illustrating the longitudinal resistance (Rxx) for Sample 4 as a function of the normalised back-gate voltage (VGS - VCNP) and the applied perpendicular magnetic field. is the longitudinal resistance Rxx and the Hall resistance Rxy plo...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97210214-BD21-4415-901E-8B81F51F42E9%7D&file=Samy_Thesis_Chapters_Compiled_FK.docx&action=default&mobileredirect=true` (152 tok): In Figure 2.5.4.6.a., the Landau fan diagram illustrating the longitudinal resistance (Rxx) for Sample 4 as a function of the normalised back-gate voltage (VGS - VCNP) and the applied perpendicular magnetic field. is the longitudinal resistance Rxx and the Hall resistance Rxy plo...

### Q14: What is the typical base temperature in the dilution refrigerator measurements?
*expected keywords: ['temperature', 'mk', 'fridge'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Lab_Instruments/Janis Photocurrent setup/Specification Sheets/LTSYS/Specifications_LTSys_CcDIL.pdf` (330 tok): ## LT SYS Low Temperature Physics Measurement System

## LT SYS -CcDIL

cryogen-free ultra low temperature physics measurement systems

:………………..……..……….…………………………………………………………….…..

| Temperature Range                                  |...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Projects/QTM%20-%20general/Design/LT%20QTM/White_paper_ANR_3DR_attoTMS.pdf` (2079 tok): atures 
above 2 K for typical cryostats, reducing either the step size (by 
reducing the voltage), or the speed (by lower ing the  drive 
frequency) can significantly decrease the dissipated h eat. To

Adding twists and turns to magneto-transport measurements  
…with attocube too...
- [3] `https://icfo.sharepoint.com/sites/TwistedMaterials-sharedequipmentandexperiments/Shared%20Documents/QTOM/Cryogenic%20Design%20and%20Documentation/LT%20QTM/White_paper_ANR_3DR_attoTMS.pdf` (2079 tok): atures 
above 2 K for typical cryostats, reducing either the step size (by 
reducing the voltage), or the speed (by lower ing the  drive 
frequency) can significantly decrease the dissipated h eat. To

Adding twists and turns to magneto-transport measurements  
…with attocube too...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Lab_Instruments/Janis Photocurrent setup/Specification Sheets/LTSYS/Specifications_LTSys_CcDIL.pdf` (266 tok): ## LT SYS Low Temperature Physics Measurement System ## LT SYS -CcDIL cryogen-free ultra low temperature physics measurement systems :........ | Temperature Range | | |----------------------------------------------------|-----------------------------------------------------------...
- [2] `/ICFO/groups/NOE/Personal/Sergi/QTM - Copy/Attocube controller/Attocube/Application Notes/AppNote P11 - ANR30 - Magneto-Transport Measurements at 40mK, 33T.pdf` (90 tok): A GaAs-heterostructure Hall-bar was mounted onto the described insert and the angle dependent Quantum Hall Effect between 0 and 52 degrees was measured at a temperature of 40 mK (see Figure 3). During a typical rotation by a few de- grees, lasting several seconds, the dilution re...
- [3] `/ICFO/groups/NOE/Lab_Instruments/Attocube CD/Application Notes/AppNote P11 - ANR30 - Magneto-Transport Measurements at 40mK, 33T.pdf` (90 tok): A GaAs-heterostructure Hall-bar was mounted onto the described insert and the angle dependent Quantum Hall Effect between 0 and 52 degrees was measured at a temperature of 40 mK (see Figure 3). During a typical rotation by a few de- grees, lasting several seconds, the dilution re...

### Q15: Explain polariton condensation in a 2D semiconductor microcavity.
*expected keywords: ['polariton', 'condensat', 'cavity'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Manuscripts/2DEP/ExPo_2D_rev_unmarked.pdf` (462 tok): that the 2DEP exhibit over two orders-of-magnitude larger wavelength confinement. Finally, we propose and numerically demonstrate two configurations for the possible experimental observation of 2DEPs.

Polaritons in 2D materials have attracted great interest in the last few years...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B6705023F-B01D-4999-BE45-0E3DF0DB4BCD%7D&file=HBC%20rv4%20L2E.docx&action=default&mobileredirect=true` (320 tok): mense progress in this field, all known nanoscale cavities are very lossy (with accordingly low quality factors, typically below ten), which impedes many prospects of strong light-matter interactions.
In principle, polaritons (and especially phonon polaritons) in 2D materials hav...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BED313EB9-1AC5-4936-AB9F-5FE19080DF01%7D&file=Poster_2D_%20Workshop_Sebastian_v2.pptx&action=edit&mobileredirect=true` (485 tok): [Slide 1] Polaritons in 2D materials are associated with strongly confined optical fields, which interact strongly with organic thin layers and gas molecules [1]. They are spectrally located in the infrared wavelength range, coinciding with the molecular vibrational resonances th...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Manuscripts/2DEP/ExPo_2D_rev_unmarked.pdf` (47 tok): When the TMD is placed in an optical cavity, these excitons can couple with cavity photons and form an out-of-plane propagating exciton-polariton [12, 13], similarly to excitons in quantum-wells....
- [2] `/ICFO/groups/NOE/Projects/HyperCavities vs Matter - Matteo/New folder/General/Thesis Proposal V4.docx` (50 tok): The interest in exploring LMI with polaritons also derives from peculiar effects observable when the confined mode carries a significant momentum, like allowing forbidden transitions in atomic states [] or observing ground state photon condensation [], or enhanced or even induced...
- [3] `/ICFO/groups/NOE/Projects/HyperCavities vs Matter - Matteo/New folder/General/TP/Thesis Proposal.docx` (50 tok): The interest in exploring LMI with polaritons also derives from peculiar effects observable when the confined mode carries a significant momentum, like allowing forbidden transitions in atomic states [] or observing ground state photon condensation [], or enhanced or even induced...

### Q16: What is the Hopfield coefficient and its role in exciton-polaritons?
*expected keywords: ['hopfield', 'exciton', 'photon'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Notebook/TopoNanop/hBN-Nanocavities_Simulation/Polariton_Simulation.pptx` (111 tok): [Slide 8] Motivation:
Hopfield theory describes a single cavity, it does not take into account a periodic system. As a result, it is difficult to adjust the theory to the polaritons obtained
Procedure:
Using polynomial fit we extract the equation of the Landau level
Cavity freque...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/Shared%20Documents/General/Manuscripts/2DEP/ExPo_2D_rev_unmarked.pdf` (462 tok): that the 2DEP exhibit over two orders-of-magnitude larger wavelength confinement. Finally, we propose and numerically demonstrate two configurations for the possible experimental observation of 2DEPs.

Polaritons in 2D materials have attracted great interest in the last few years...
- [3] `/ICFO/groups/NOE/Meetings/Group presentations/ExcitonPolaritonMeeting16112017_KJT.pptx` (126 tok): [Slide 6] Next steps
Measure existence of exciton-polariton modes and coupling of emitters to these modes
Measure emission enhancement using antenna to couple to the far field
Measure ion-polariton-ion coupling (superradiance)
Matching exciton-RE, IR

Erbium, 1.5 mm



Black phos...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Notebook/TopoNanop/hBN-Nanocavities_Simulation/Polariton_Simulation.pptx` (0 tok): ...
- [2] `/opt/qnoe-agent/repos/QED-phqh/logbook/2026-03-16.md` (93 tok): Note: the Hopfield model has no coupling between the phonon modes, but the LL transition effectively couple the phonon modes, and provide for the mode repulsion. If each phonon-polariton mode couples to the LL transition through a different matrix element (different polarisation,...
- [3] `/opt/qnoe-agent/repos/QED-phqh/SLG09-C4/spectroscopy_analysis/quantitative_analysis_py_RB/scripts/vf_model_interactive_marimo.py` (0 tok): ...

### Q17: How does hBN encapsulation improve graphene device quality?
*expected keywords: ['hbn', 'encapsulat', 'mobility'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B5F0F99E9-4D70-4181-BDAB-2FEE3637293D%7D&file=Referee_Reply_Round1.docx&action=default&mobileredirect=true` (304 tok): esearch community routinely encapsulates graphene devices now so perhaps the quality of unencapsulated graphene has improved due to improved exfoliation and cleaning techniques but no one has noticed?
With the previous methods employed, the quality of graphene can be high but can...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B8975C08C-CDA2-4463-9710-2AF674AECFEE%7D&file=Perspective_Paper_ICFO_V2.docx&action=default&mobileredirect=true` (369 tok): TMDs for graphene encapsulation
The integration of two-dimensional (2D) materials into complementary metal-oxide-semiconductor (CMOS) technologies marks a transformative era in the evolution of electronic devices, offering the potential for significantly improved performance and...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_abstract_V1.docx` (366 tok): xagonal boron nitride (hBN), into Complementary Metal-Oxide-Semiconductor CMOS platforms, paving the way for innovative optoelectronic devices with improved functionality to overcome these challenges.
This thesis investigates the crucial role of encapsulants and substrates in gra...

**Provence top-3 (pruned):**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B5F0F99E9-4D70-4181-BDAB-2FEE3637293D%7D&file=Referee_Reply_Round1.docx&action=default&mobileredirect=true` (42 tok): This has been developed by scanning probe microscopy groups using the so-called “stack and flip” method, in which hBN picks up graphene and then turns upside down ensuring a pristine surface (see reference 20)....
- [2] `/ICFO/groups/NOE/Projects/Waveguide-coupled Modulators HfO2/8_publication/05. Referee reply/Referee reply_BT_v7.docx` (122 tok): First, we started with high-quality hBN encapsulated modulators (see Fig. Thus, we integrated a high-k dielectric (HfO2) between two hBN flakes to increase the dielectric performance while still maintaining the high quality of graphene. Apart from increasing the robustness of the...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B8975C08C-CDA2-4463-9710-2AF674AECFEE%7D&file=Perspective_Paper_ICFO_V2.docx&action=default&mobileredirect=true` (210 tok): State-of-the-art high mobility graphene-based devices typically rely on exfoliated multilayer hexagonal boron nitride (hBN) encapsulation4,5,7,8. This approach leverages the exceptional properties of hBN, such as its atomically smooth, dangling-bond-free surface and excellent ins...

### Q18: What signatures indicate the quantum Hall effect in the transport data?
*expected keywords: ['quantum hall', 'plateau', 'filling'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_High_quality_heterostructure_paperpal_V3.docx` (504 tok): n of normalised back-gate voltage (VGS - VCNP). b, Comparison of the Drude mobility (blue curve) and the hall mobility (red curve) to the carrier density n, where the black dashed line indicates the .
Subsequently, magneto-transport measurements were conducted on sample 4 to gain...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B7F860C0C-93E3-4CE4-A4F8-16C531453277%7D&file=Samy_Thesis_Chapters_Compiled.docx&action=default&mobileredirect=true` (409 tok): obility calculated from the  and the Hall mobility  (where, ) is compared and the plot exhibits a perfect match when , validating the analysis performed using  in the previous section of this chapter.
Figure 2.5.4.5., Hall measurements of the TFSI treated Hallbar adapted and repr...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B97210214-BD21-4415-901E-8B81F51F42E9%7D&file=Samy_Thesis_Chapters_Compiled_FK.docx&action=default&mobileredirect=true` (409 tok): obility calculated from the  and the Hall mobility  (where, ) is compared and the plot exhibits a perfect match when , validating the analysis performed using  in the previous section of this chapter.
Figure 2.5.4.5., Hall measurements of the TFSI treated Hallbar adapted and repr...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_High_quality_heterostructure_paperpal_V3.docx` (295 tok): 6. a. Landau fan diagram illustrating the longitudinal resistance (Rxx) for Sample 4 as a function of the normalized back-gate voltage (VGS–VCNP) and the applied perpendicular magnetic field. The Landau fan diagram vividly portrays quantum Hall states (QHS), highlighting the high...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BDC5FB91C-CD2F-4692-9BA3-6C715F8EFEBA%7D&file=Samy_Thesis_Chapter_2_High_quality.docx&action=default&mobileredirect=true` (156 tok): The Landau fan diagram vividly portrays quantum Hall states (QHS), highlighting the high-quality nature of the graphene encapsulated by the treated WS2. is the longitudinal resistance Rxx and the Hall resistance Rxy plotted as a function of the magnetic field taken at the gate vo...
- [3] `/ICFO/groups/NOE/Theses & reports/PhD/Samy/Samy_Thesis_High_quality_heterostructure.docx` (156 tok): The Landau fan diagram vividly portrays quantum Hall states (QHS), highlighting the high-quality nature of the graphene encapsulated by the treated WS2. is the longitudinal resistance Rxx and the Hall resistance Rxy plotted as a function of the magnetic field taken at the gate vo...

### Q19: Describe the git branching and pull request workflow for the group repos.
*expected keywords: ['branch', 'pull request', 'commit'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `/opt/qnoe-agent/repos/QNOE-group-info/docs/github-usage.md` (400 tok): `** — bug fix.
- **`yourname/topic`** — personal or experimental work.

Create a branch: `git checkout -b feature/my-feature`  
Switch back to main: `git checkout main`

---

## 5. Pull Requests (PRs)

1. Push your branch (see above).
2. On GitHub: open the repo → you’ll often se...
- [2] `/opt/qnoe-agent/repos/QNOE-group-info/docs/github-usage.md` (473 tok): # GitHub usage guide for the lab

Short guide to using GitHub for lab repos: cloning, branching, and contributing.

---

## 1. Get access

- Create a [GitHub account](https://github.com/join) if you don’t have one.
- Ask the lab admin to add you to the **organization** or as **co...
- [3] `/opt/qnoe-agent/repos/QNOE-group-info/workshop/github_workshop_action_plan.md` (499 tok): # Git & GitHub workshop — 30 min

Hands-on intro for research groups · one shared repo, one file, personal branches

---

## Setup — before the session

**Prepare the repo** `[you]`  
Create a GitHub repo with a single `participants.md` file (just a header, no names). Make sure e...

**Provence top-3 (pruned):**
- [1] `/opt/qnoe-agent/repos/QNOE-group-info/workshop/github_workshop_action_plan.md` (340 tok): `[you]` Repo, commit, branch, pull request — one sentence each. Show the repo on screen. Explain the plan: everyone adds their name, you merge everything at the end. ```bash git clone <repo-url> ``` **7–10'** · Create a personal branch `[everyone]` Each person creates their own b...
- [2] `/opt/qnoe-agent/repos/QNOE-group-info/docs/github-usage.md` (226 tok): Daily workflow (edit → commit → push) ```bash # 1. Update your local copy git pull # 2. Create a branch for your work (recommended) git checkout -b feature/my-change # 3. Edit files, then stage and commit git add . git commit -m "Short description of what you did" # 4. Push your...
- [3] `/opt/qnoe-agent/repos/QNOE-group-info/docs/github-usage.md` (255 tok): `** — bug fix. - **`yourname/topic`** — personal or experimental work. Create a branch: `git checkout -b feature/my-feature` Switch back to main: `git checkout main` --- ## 5. Pull Requests (PRs) 1. Push your branch (see above). 2. On GitHub: open the repo → you’ll often see “Com...

### Q20: What superconducting materials are studied and how is Tc determined?
*expected keywords: ['superconduct', 'tc', 'critical'] · CE kw hit: True · Prov kw hit: True*

**Cross-encoder top-3:**
- [1] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7BDA708C93-4694-4E49-8FF4-D1FF0CA0A3A7%7D&file=AIE2025_proposal.docx&action=default&mobileredirect=true` (382 tok): superconducting transition (Tc ≈ 80-110 K depending on BSCCO phase) will provide unique insights into how the thermoelectric properties evolve locally as the material enters the superconducting state.
•          Complementary Multi-Scale Information: Combining far-field (micron-s...
- [2] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B41BDAA65-F284-4097-969F-95CC7F860510%7D&file=NehaBhatia_Training%20plan.docx&action=default&mobileredirect=true` (276 tok): Research Goal :
Study light-matter interaction in correlated high-Tc superconducting cuprate Bi2Sr2CaCu2O8 (BSCCO).
Research Project :
During the trainee period, the focus will be on studying light-matter interaction in the high-temperature superconducting cuprate BSCCO. This mat...
- [3] `/ICFO/groups/NOE/Notebook/TopoNanop/BSCCO/BSCCO_cryoSNOM_design_of_experiment/s41598-017-03408-2.pdf` (1105 tok): 1
Scientific  RepoRts  | 7: 3295  | DOI:10.1038/s41598-017-03408-2
www.nature.com/scientificreports
Growth of high-quality Bi2Sr2 
CaCu2O8+δ whiskers and electrical 
properties of resulting exfoliated 
flakes
Apoorv Jindal, Digambar A. Jangade, Nikhil Kumar, Jaykumar Vaidya, Ipsi...

**Provence top-3 (pruned):**
- [1] `/ICFO/groups/NOE/Notebook/TopoNanop/BSCCO/BSCCO_cryoSNOM_design_of_experiment/s41598-017-03408-2.pdf` (259 tok): We observe a superconducting critical temperature, Tc, of 86 K. We map the evolution of the critical current as a function of temperature. Thin flakes of NbSe 2, TaS2, and FeSe have been discovered to be superconducting, fuelling the progress in this field4–6. Bi2Sr2CaCu2O8+δ (BS...
- [2] `/opt/qnoe-agent/repos/Superconductivity/Superconductivity_Meeting_Notes/Superconductivity-Meeting-Notes.md` (97 tok): # Superconductivity Meeting Notes ## 2026-05-15 ### Device D4: BSCCOxMoO3 + BSCCOxhBN. Neha’s data: Calculation of the transition temperatures: Tc_mean is the inflection point (dR/dT is maximal), Tc_slope0 where the sign of derivative changes. Questions regarding the determinatio...
- [3] `https://icfo.sharepoint.com/sites/NOE-Group/_layouts/15/Doc.aspx?sourcedoc=%7B41BDAA65-F284-4097-969F-95CC7F860510%7D&file=NehaBhatia_Training%20plan.docx&action=default&mobileredirect=true` (97 tok): Research Goal : Study light-matter interaction in correlated high-Tc superconducting cuprate Bi2Sr2CaCu2O8 (BSCCO). Research Project : During the trainee period, the focus will be on studying light-matter interaction in the high-temperature superconducting cuprate BSCCO. This mat...