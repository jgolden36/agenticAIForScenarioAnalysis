data_packages <- c(
  "dplyr", "tidyr", "leaflet", 
  "leaflet.extras", "leaflet.minicharts", 
  "ggplot2", "tidyverse", "mapview", "webshot"
)

# Funktion, die Packages installiert und lädt, falls sie das noch nicht sind
check_packages <- lapply(data_packages, FUN = function(x) {
  if (!require(x, character.only = TRUE)) {
    install.packages(x, dependencies = TRUE)
    library(x, character.only = TRUE)
  }
})

rm(data_packages)
rm(check_packages)

##### The following lines determine the layout of the plots ########

coloring <- c(
  "#5cbec9", #turquoise
  "#d5d10e", #green-yellow
  "#00509e", #NTNU blue 
  "#f1d282", #beige
  "#79a2ce", #blue
  "#f58025", #orange
  "#c9d4b2", #green
  "#dde7ee", #lightblue
  "#552988", #purple
  "#404040"  #grey
)


# Define sizes of legends
fonts <- theme(
  axis.text = element_text(size = 18), 
  legend.text = element_text(size = 20),
  legend.title = element_text(size = 20), 
  axis.title = element_text(size = 20, vjust = 1), 
  strip.text = element_text(size = 20),
  plot.title = element_text(size = 24, face = "bold", hjust = 0.5, vjust=1)
)

# Define theme used
theme_plot <- theme_gray()

# Define colours for look of the graphs
#col_years <- coloring[5:length(coloring)]
col_scen <- coloring[3:length(coloring)]
col_cap <- coloring[1:2]

save(fonts, theme_plot, col_scen, col_cap, file = "layoutPlot.RData")

#### End of plot layout - other details adjusted in each plot ######

rm(coloring)

"End of execution. Execution successful"
