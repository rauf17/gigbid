# ADR 0002: Student-built GigSim and synthetic data
**Status:** accepted

The instructor's GigSim, persona corpora and dev set were not distributed (class thread
confirmed students build their own). We build a replaceable GigSim (`gigsim/`, frozen by hash
after completion), persona corpora from Kaggle job data plus clearly-labelled synthetic
portfolios, and a gold dev set. Everything synthetic is marked as such in docs/DATA_CARD.md.
