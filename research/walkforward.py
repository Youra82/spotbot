import sys
import numpy as np, pandas as pd
pref = sys.argv[1] if len(sys.argv) > 1 else 'grid2'
M = np.load(f'{pref}_rets.npy').astype(np.float64)
P = pd.read_csv(f'{pref}_params.csv')
idx = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(f'{pref}_index.csv').iloc[:, 0], utc=True)).tz_localize(None)
def metr(r):
    e = np.cumprod(1 + r, axis=-1)
    yrs = r.shape[-1] / 365.25
    cagr = e[..., -1] ** (1 / yrs) - 1
    dd = (e / np.maximum.accumulate(e, axis=-1) - 1).min(axis=-1)
    return cagr, dd
# Nachbarschaft fuer Robust-Score
keys = list(P.columns); vals = {k: sorted(P[k].unique()) for k in keys}
lut = {tuple(r): i for i, r in enumerate(P.itertuples(index=False))}
nbrs = []
for i, r in enumerate(P.itertuples(index=False)):
    out = []
    for j, k in enumerate(keys):
        vs = vals[k]; p = vs.index(r[j])
        for q in (p - 1, p + 1):
            if 0 <= q < len(vs):
                t = list(r); t[j] = vs[q]; out.append(lut.get(tuple(t)))
    nbrs.append([o for o in out if o is not None])
def select(tr, rule, ddcap):
    cagr, dd = metr(tr)
    feas = dd > ddcap
    if rule == 'cagr':
        s = np.where(feas, cagr, -np.inf)
    elif rule == 'calmar':
        s = np.where(feas, cagr / -dd, -np.inf)
    elif rule == 'robust':
        nb = np.array([np.median(cagr[n]) if n else -1 for n in nbrs])
        nbf = np.array([np.mean(feas[n]) if n else 0 for n in nbrs])
        s = np.where(feas & (nbf >= 0.5), np.minimum(cagr, nb), -np.inf)
    return int(np.argmax(s))
start = np.searchsorted(idx, pd.Timestamp('2018-01-01'))
for rule in ['cagr', 'calmar', 'robust']:
    for ddcap in [-0.20, -0.25, -0.30]:
        oos = []; picks = []
        for Y in range(2020, 2027):
            a = np.searchsorted(idx, pd.Timestamp(f'{Y}-01-01')); b = np.searchsorted(idx, pd.Timestamp(f'{Y + 1}-01-01'))
            k = select(M[:, start:a], rule, ddcap)
            oos.append(M[k, a:b]); picks.append(k)
        r = np.concatenate(oos); c, dd = metr(r)
        yr = [f'{(np.prod(1 + o) - 1) * 100:5.0f}' for o in oos]
        vt = [P.vol_target[k] for k in picks]
        print(f'{rule:7s} cap{ddcap:.2f}: WF 2020-26 CAGR {c * 100:5.1f}%  maxDD {dd * 100:6.1f}%  Endwert x{np.prod(1 + r):6.1f} | Jahre {yr} | vt {vt}')
