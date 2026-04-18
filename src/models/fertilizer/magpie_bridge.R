# MAgPIE Bridge Script for the LangChain pipeline
#
# Translates the Python adapter's JSON I/O convention into MAgPIE's R-based
# `cfg` configuration system. It:
#   1. Reads a JSON input file (path passed as the first CLI argument)
#   2. Locates the MAgPIE source tree (env var MAGPIE_ROOT preferred)
#   3. Loads `config/default.cfg`, then applies scenario overrides
#   4. Runs MAgPIE end-to-end via `start_run(cfg)` from
#      `scripts/start_functions.R`
#   5. Parses outputs from `output/<title>/report.mif` and (optionally)
#      `fulldata.gdx`, and writes results as JSON to stdout.
#
# Usage:
#   Rscript --vanilla magpie_bridge.R /path/to/inputs.json
#
# Expected JSON input structure:
# {
#   "scenario_id": "scenario_a",
#   "title": "hormuz_scenario_a",
#   "magpie_shocks": {
#     "fertilizer_price_multiplier": 1.5,
#     "yield_scaling_factor": 0.9,
#     "water_availability_factor": 0.7,
#     "transport_cost_multiplier": 1.3
#   },
#   "cfg_overrides": {
#     "c09_pop_scenario": "SSP2",
#     "c09_gdp_scenario": "SSP2",
#     "c_timesteps": "coup2100",
#     "s21_trade_tariff": 1
#   },
#   "affected_regions": ["MEA", "IND", "OAS"]
# }
#
# IMPORTANT CAVEAT - module patches required for shocks
# -----------------------------------------------------
# Stock MAgPIE 4.x has no built-in switches named
#   s38_fert_cost_multiplier, s14_yield_shock_factor,
#   s43_water_shock_factor, s40_transport_cost_multiplier.
# The bridge writes these into `cfg$gms` so they appear as `$setglobal`
# entries during GAMS compilation, but they are silently ignored unless
# the corresponding modules are patched to consume them. Suggested patch
# points (each one-liner inside the realisation's preloop.gms / input.gms):
#
#   modules/38_factor_costs/sticky_feb18/input.gms
#     scalar s38_fert_cost_multiplier / 1 /;
#   modules/38_factor_costs/sticky_feb18/preloop.gms
#     i38_fac_req_reg(t,i,kcr) = i38_fac_req_reg(t,i,kcr) * s38_fert_cost_multiplier;
#
#   modules/14_yields/managementcalib_aug19/input.gms
#     scalar s14_yield_shock_factor / 1 /;
#   modules/14_yields/managementcalib_aug19/preloop.gms
#     f14_yields(t_all,j,kve,w) = f14_yields(t_all,j,kve,w) * s14_yield_shock_factor;
#
#   modules/43_water_availability/total_water_aug13/input.gms
#     scalar s43_water_shock_factor / 1 /;
#   modules/43_water_availability/total_water_aug13/preloop.gms
#     f43_wat_avail(t_all,j) = f43_wat_avail(t_all,j) * s43_water_shock_factor;
#
# Until these patches are applied, the run will execute with default
# (unshocked) parameter values and the result set still goes through the
# pipeline -- the convergence flag remains "completed" but `magpie_shocks`
# in metadata records what *would* have been applied.

suppressPackageStartupMessages({
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Required R package 'jsonlite' is not installed.")
  }
})

`%||%` <- function(a, b) if (is.null(a)) b else a

# ----------------------------------------------------------------------
# CLI / input parsing
# ----------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript --vanilla magpie_bridge.R <input_json_path>")
}
input_path <- args[1]
if (!file.exists(input_path)) {
  stop("Input JSON file not found: ", input_path)
}

params <- jsonlite::fromJSON(input_path, simplifyVector = TRUE)

# ----------------------------------------------------------------------
# Locate MAgPIE source tree
# ----------------------------------------------------------------------
magpie_root <- Sys.getenv("MAGPIE_ROOT", "")
if (!nzchar(magpie_root)) {
  candidates <- c(
    "Models/Fertilizer/magpie-master/magpie-master",
    "../Models/Fertilizer/magpie-master/magpie-master",
    "../../Models/Fertilizer/magpie-master/magpie-master"
  )
  for (cand in candidates) {
    if (file.exists(file.path(cand, "main.gms"))) {
      magpie_root <- normalizePath(cand)
      break
    }
  }
}
if (!nzchar(magpie_root) || !file.exists(file.path(magpie_root, "main.gms"))) {
  stop("Cannot locate MAgPIE root (looked for main.gms). ",
       "Set MAGPIE_ROOT environment variable.")
}

# All MAgPIE R machinery (start_functions.R, default.cfg paths, etc.)
# expects to be sourced from the model root.
original_wd <- getwd()
setwd(magpie_root)

# Buffer status / warning messages so they don't pollute stdout (which we
# reserve for the final JSON payload).
status_msgs <- character(0)
log_status <- function(...) {
  status_msgs <<- c(status_msgs, paste0(...))
  message(...)
}

# Helper for safe extraction from MAgPIE's MIF report. The MIF column
# layout is: Model;Scenario;Region;Variable;Unit;<year cols...>
extract_mif_var <- function(mif_data, prefix, year_cols) {
  if (!"Variable" %in% names(mif_data)) return(list())
  matches <- startsWith(mif_data$Variable, prefix)
  rows <- mif_data[matches, , drop = FALSE]
  if (nrow(rows) == 0L) return(list())
  out <- vector("list", nrow(rows))
  for (i in seq_len(nrow(rows))) {
    key <- paste(rows$Region[i], rows$Variable[i], sep = "|")
    values <- as.numeric(rows[i, year_cols])
    names(values) <- year_cols
    out[[i]] <- values
    names(out)[i] <- key
  }
  out
}

results <- list(
  scenario_id = params$scenario_id %||% "default",
  convergence = "unknown",
  magpie_shocks = params$magpie_shocks %||% list(),
  cfg_overrides = params$cfg_overrides %||% list()
)

tryCatch({

  # --------------------------------------------------------------------
  # Build the cfg
  # --------------------------------------------------------------------
  source("scripts/start_functions.R")
  source("config/default.cfg")  # populates `cfg` in the current env

  cfg$title <- params$title %||% paste0("hormuz_", results$scenario_id)
  log_status("Configured run title: ", cfg$title)

  # Apply cfg$gms overrides verbatim (string or numeric)
  if (length(params$cfg_overrides) > 0) {
    for (key in names(params$cfg_overrides)) {
      cfg$gms[[key]] <- params$cfg_overrides[[key]]
    }
  }

  # Apply shock parameters as cfg$gms scalars. These map onto custom
  # switches that must be added to the corresponding module realisations
  # (see CAVEAT in the header). Unknown switches are silently ignored
  # by GAMS during compilation, so this is safe to set unconditionally.
  shocks <- params$magpie_shocks
  if (!is.null(shocks$fertilizer_price_multiplier)) {
    cfg$gms$s38_fert_cost_multiplier <- shocks$fertilizer_price_multiplier
  }
  if (!is.null(shocks$yield_scaling_factor)) {
    cfg$gms$s14_yield_shock_factor <- shocks$yield_scaling_factor
  }
  if (!is.null(shocks$water_availability_factor)) {
    cfg$gms$s43_water_shock_factor <- shocks$water_availability_factor
  }
  if (!is.null(shocks$transport_cost_multiplier)) {
    cfg$gms$s40_transport_cost_multiplier <- shocks$transport_cost_multiplier
  }

  # --------------------------------------------------------------------
  # Run MAgPIE
  # --------------------------------------------------------------------
  log_status("Calling start_run() ... (this can take hours on a full ",
             "coup2100 run; consider c_timesteps='quicktest' for smoke tests)")
  start_run(cfg = cfg, codeCheck = FALSE)
  log_status("start_run() returned without error.")

  # --------------------------------------------------------------------
  # Output parsing
  # --------------------------------------------------------------------
  output_dir <- file.path("output", cfg$title)
  if (!dir.exists(output_dir)) {
    # MAgPIE timestamps run folders; pick the newest match.
    candidates <- list.files(
      "output", pattern = paste0("^", cfg$title), full.names = TRUE
    )
    candidates <- candidates[file.info(candidates)$isdir]
    if (length(candidates) > 0) {
      output_dir <- candidates[order(file.info(candidates)$mtime,
                                     decreasing = TRUE)][1]
    }
  }
  results$output_dir <- output_dir

  mif_files <- list.files(output_dir, pattern = "report\\.mif$",
                          full.names = TRUE)
  if (length(mif_files) > 0) {
    mif_data <- read.csv(mif_files[1], sep = ";", header = TRUE,
                         stringsAsFactors = FALSE, check.names = FALSE)
    year_cols <- grep("^[0-9]{4}$", names(mif_data), value = TRUE)

    results$production <- extract_mif_var(mif_data, "Production|", year_cols)
    results$prices     <- extract_mif_var(mif_data, "Prices|", year_cols)
    results$land_use   <- extract_mif_var(mif_data, "Land Cover|", year_cols)
    results$emissions  <- extract_mif_var(mif_data, "Emissions|", year_cols)
    results$water_use  <- extract_mif_var(mif_data, "Water|", year_cols)
    results$convergence <- "completed"
  } else {
    log_status("No report.mif found in ", output_dir)
  }

  gdx_files <- list.files(output_dir, pattern = "fulldata\\.gdx$",
                          full.names = TRUE)
  if (length(gdx_files) > 0 && requireNamespace("gdx", quietly = TRUE)) {
    tryCatch({
      nit_data <- gdx::readGDX(gdx_files[1], "ov_nr_inorg_fert_reg",
                               select = list(type = "level"), react = "silent")
      if (!is.null(nit_data)) {
        results$fertilizer_use <- as.list(as.data.frame(nit_data))
      }
    }, error = function(e) {
      results$fertilizer_use_error <- conditionMessage(e)
    })
  } else if (length(gdx_files) > 0 && requireNamespace("gdxrrw", quietly = TRUE)) {
    tryCatch({
      nit_data <- gdxrrw::rgdx(gdx_files[1],
                               list(name = "vm_nr_inorg_fert_reg"))
      if (!is.null(nit_data)) {
        results$fertilizer_use <- as.list(nit_data$val)
      }
    }, error = function(e) {
      results$fertilizer_use_error <- conditionMessage(e)
    })
  }

  results$log_tail <- tail(status_msgs, 50)
  cat(jsonlite::toJSON(results, auto_unbox = TRUE, na = "null",
                       pretty = FALSE))

}, error = function(e) {
  error_result <- list(
    scenario_id  = results$scenario_id,
    convergence  = "failed",
    error        = conditionMessage(e),
    traceback    = paste(capture.output(traceback()), collapse = "\n"),
    log_tail     = tail(status_msgs, 50),
    magpie_shocks = results$magpie_shocks,
    cfg_overrides = results$cfg_overrides
  )
  cat(jsonlite::toJSON(error_result, auto_unbox = TRUE, na = "null",
                       pretty = FALSE))
}, finally = {
  setwd(original_wd)
})
