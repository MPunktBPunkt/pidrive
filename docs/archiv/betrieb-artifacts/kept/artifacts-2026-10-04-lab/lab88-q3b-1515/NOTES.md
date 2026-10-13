# Q3b Prefill Lab — `lab88-q3b-1515`

**Verdict:** `PASS`
**FW:** `0.4.43-dev` · Serial `PD0042`
**Prefill:** fromOff=348160 (abs LBA 761)

## Results
- Test A (seed A / Oracle A+host): **True**
- Test B (seed B SoftAP / no remount): **True**
- Test C (burst after A→B / Oracle B+C / head frozen / LBA761=B): **True**
- Control (stay/return A, no remount): **True**

## Oracles
- **A** SoftAP `/api/lab/body_read` == expected Q3B1 pattern
- **B** Host issued post-switch reads for burst LBAs (lab-simulated)
- **C** Host `dd` MSC response bytes == expected pattern

## Geometry
- Scan head: LBA 81..760 (frozen hash 76174bce4a0c8783)
- Prefill body: LBA >= 761
- Do not start prefill at 1953 — burst also reads 761..1952
