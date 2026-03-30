*Combine all latest results gdx versions of the listed scenario combinations,
* in Excel to facilitate Figure creation in Excel
*The gdx results versions are created at the end of reports.gms

$call gdxmerge gdx\NPS-Ref.gdx gdx\SDS-Vision.gdx o=gdx\merged
;

execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_cal_rgn.xlsx      par=rep_cal_rgn     rng=cal_rgn!A2   rDim=4 cDim=2';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_cal_cn.xlsx       par=rep_cal_cn      rng=cal_cn!A2    rDim=5 cDim=2';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_mass_bal.xlsx     par=rep_mass_bal    rng=mass_bal!A2  rDim=7 cDim=2';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_infra_pipe.xlsx   par=rep_infra_pipe  rng=pipe!A2      rDim=8 cDim=0';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_infra_liquef.xlsx par=rep_infra_liq   rng=liquef!A2    rDim=6 cDim=0';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_infra_regas.xlsx  par=rep_infra_regas rng=regas!A2     rDim=6 cDim=0';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_infra_stor.xlsx   par=rep_infra_stor  rng=stor!A2      rDim=8 cDim=0';
execute 'gdxxrw gdx\merged.gdx o=excel\SET-Nav_all_trade.xlsx        par=rep_IAMC_supply rng=trade!A2     rDim=6 cDim=0';
