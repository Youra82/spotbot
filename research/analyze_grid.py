import sys
import numpy as np, pandas as pd
f = sys.argv[1] if len(sys.argv) > 1 else 'grid1.csv'
DDMAX = -30.0
g = pd.read_csv(f)
params = [c for c in g.columns if not c.startswith(('is_', 'oos_', 'full_'))]
g[params] = g[params].astype(str)
print('Kombis', len(g))
feas = g[g.is_maxdd > DDMAX]
print('IS-DD<=30%:', len(feas))
# Nachbarschafts-Robustheit: Median IS-CAGR aller Kombis, die sich in genau 1 Parameter unterscheiden
key = g[params].apply(tuple, axis=1)
lut = dict(zip(key, g.index))
vals = {p: sorted(g[p].unique(), key=lambda x: (len(x), x)) for p in params}
def neigh(row):
    out = []
    for j, p in enumerate(params):
        vs = vals[p]; k = vs.index(row[p])
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(vs):
                t = list(row[params]); t[j] = vs[kk]
                if tuple(t) in lut: out.append(lut[tuple(t)])
    return out
rows = []
for i, r in feas.iterrows():
    nb = g.loc[neigh(r)]
    rows.append((i, nb.is_cagr.median(), (nb.is_maxdd > DDMAX).mean(), nb.is_maxdd.min()))
nbdf = pd.DataFrame(rows, columns=['i', 'nb_cagr', 'nb_feas', 'nb_worstdd']).set_index('i')
feas = feas.join(nbdf)
feas['score'] = np.minimum(feas.is_cagr, feas.nb_cagr)
cols = params + ['is_cagr', 'is_maxdd', 'nb_cagr', 'nb_feas', 'oos_pnl', 'oos_maxdd', 'full_cagr', 'full_maxdd', 'full_sharpe']
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print('\n=== Top 15 nach robustem IS-Score (min(IS-CAGR, Nachbar-Median)) ===')
print(feas.sort_values('score', ascending=False)[cols].head(15).round(1).to_string())
print('\n=== Ehrliche Verteilung: OOS aller IS-zulaessigen Kombis ===')
print(feas[['oos_pnl', 'oos_maxdd', 'oos_cagr']].describe().round(1))
top = feas.sort_values('score', ascending=False).head(50)
print('\nTop-50 (IS-robust) OOS: median pnl %.0f%%, median dd %.1f, Anteil OOS-DD<=30%%: %.2f' %
      (top.oos_pnl.median(), top.oos_maxdd.median(), (top.oos_maxdd > DDMAX).mean()))
feas.to_csv(f.replace('.csv', '_feas.csv'))
