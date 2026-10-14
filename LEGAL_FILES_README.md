# Legal Files Reference

This document explains the legal and compliance files included in the GraphAide repository.

## Files in Repository Root

All of these files are in the project root directory:

| File | Purpose | Audience |
|------|---------|----------|
| **LICENSE.txt** | BSD 2-Clause License terms | Developers, lawyers |
| **DISCLAIMER** | Government disclaimer and liability limitations | All users |
| **ACKNOWLEDGMENT** | Credits, funding, and research citations | Researchers, academics |
| **NOTICE** | Software identification and legal notices | Compliance officers |

## Files in Documentation

Markdown versions of legal files are also included in the documentation site at `docs/legal/`:

| File | URL |
|------|-----|
| **license.md** | https://pnnl.github.io/GraphAide/legal/license.md |
| **disclaimer.md** | https://pnnl.github.io/GraphAide/legal/disclaimer.md |
| **acknowledgment.md** | https://pnnl.github.io/GraphAide/legal/acknowledgment.md |
| **notice.md** | https://pnnl.github.io/GraphAide/legal/notice.md |

## Quick Overview

### LICENSE.txt
- **What it is:** BSD 2-Clause (Simplified BSD) License
- **Key points:**
  - You can use, modify, and distribute GraphAide
  - You can use it for commercial purposes
  - You must include the license text in distributions
  - You must attribute the original copyright holder
  - Software is provided "AS IS" with no warranties

### DISCLAIMER
- **What it is:** Government disclaimer required by DOE funding
- **Key points:**
  - GraphAide is provided without warranties
  - No guarantee of accuracy or completeness
  - Developers not liable for damages from use
  - Government statement required for funded research
  - Data validation is user's responsibility

### ACKNOWLEDGMENT
- **What it is:** Recognition of authors, contributors, and funding
- **Key points:**
  - Lists lead developers and contributors
  - Acknowledges DOE funding and PNNL support
  - Provides research citation in BibTeX format
  - Thanks open-source dependencies
  - Provides contact information

### NOTICE
- **What it is:** Comprehensive legal and compliance notice
- **Key points:**
  - Software identification and version info
  - Restrictions and permitted uses
  - Export control statements
  - Data privacy considerations
  - Limitations of liability
  - Government rights statement

## How These Files Are Referenced

### In Repository
```
README.md
  ↓
  References LICENSE.txt, DISCLAIMER, ACKNOWLEDGMENT, NOTICE
  
mkdocs.yml
  ↓
  nav:
    - Legal:
        - License: legal/license.md
        - Disclaimer: legal/disclaimer.md
        - Acknowledgment: legal/acknowledgment.md
        - Notice: legal/notice.md
```

### In Documentation Website
```
https://pnnl.github.io/GraphAide
  ↓
  Home page footer has link to Legal section
  ↓
  https://pnnl.github.io/GraphAide/legal/
  ↓
  Shows all four legal documents
```

### In PyPI Package
```
pyproject.toml
  ↓
  license = {text = "BSD 2-Clause"}
  
Package metadata includes LICENSE.txt
```

## Important Points for Users

### Before Using GraphAide

1. **Read the DISCLAIMER** — Understand limitations
2. **Review the NOTICE** — Know what you're getting
3. **Check LICENSE.txt** — Understand usage rights

### If Using for Research

1. **Use the citation** from ACKNOWLEDGMENT in your papers
2. **Credit PNNL and DOE** in acknowledgments
3. **Follow proper attribution** in any derivative works

### If Using Commercially

1. **Comply with BSD License** — Include license text
2. **Validate results** — No warranties provided
3. **Handle data securely** — You're responsible for data protection

### If Experiencing Issues

1. **Check the NOTICE** for export/legal restrictions
2. **Review the DISCLAIMER** for liability limitations
3. **Contact support** at sumit.purohit@pnnl.gov

## Updating Legal Files

When updating version or legal terms:

1. Update `.txt` files in repository root
2. Update corresponding `.md` files in `docs/legal/`
3. Update date stamps in legal documents
4. Update version number if applicable
5. Update `pyproject.toml` if license changes
6. Commit all changes together

## Distribution Requirements

When distributing GraphAide (in any form):

1. **Include LICENSE.txt** — Required by BSD License
2. **Include DISCLAIMER** — Required by DOE funding
3. **Include ACKNOWLEDGMENT** — Proper attribution
4. **Include NOTICE** — Legal compliance
5. **Reference** these files in any README or documentation

## Government and Compliance

### DOE/PNNL Compliance
- GraphAide is developed with U.S. Department of Energy funding
- PNNL is a multiprogram national laboratory
- Government retains non-exclusive rights to use software
- Export control regulations may apply

### PNNL Information Release
- **PNNL Release Number:** PNNL-SA-205147
- Indicates this software has been cleared for public release
- Subject to government export control review

## Need Help?

- **Licensing questions?** Contact sumit.purohit@pnnl.gov
- **Legal compliance?** Review NOTICE.md
- **Liability questions?** See DISCLAIMER
- **Attribution?** Use citation from ACKNOWLEDGMENT

---

**Last Updated:** October 2026  
**Status:** All legal files in place and documented
