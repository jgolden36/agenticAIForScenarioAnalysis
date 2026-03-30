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

load("data_world.RData")
load("layoutPlot.RData")

#make plot for production
ggplot(
  data = filter(plot_data_world, Type == "Prod" &
                  Year %in% c("2015", "2030", "2050") ), 
  aes(reorder(Region, Capacity), 
      y = Capacity, fill = Scen)
  )+
  geom_bar(stat = "identity", position = "dodge", width=0.85) + 
  scale_fill_manual(values = col_scen, 
                    name = "Production in"
  )+
  theme_plot+
  coord_flip() + 
  labs(title = "Gas production pattern for world regions in two scenarios", 
       x = "Region", 
       y = "Production in bcm per year")+
  fonts +
  facet_wrap(~Year) +
ggsave(width = 18, 
       height = 10, 
       dpi = 300, 
       filename = "Plots/bar_plot_world_PROD.pdf")

#make plot for consumption
ggplot(
  data = filter(plot_data_world, Type == "Cons" &
                  Year %in% c("2015", "2030", "2050") ), 
  aes(reorder(Region, Capacity),
      y = Capacity, fill = Scen)
  )+
  geom_bar(stat = "identity", position="dodge", width=0.85) + 
  scale_fill_manual(values= col_scen, 
                    name= "Consumption in"   
  )+
  theme_plot+
  coord_flip() + 
  labs(title="Gas consumption pattern for world regions in two scenarios", 
       x = "Region", 
       y = "Consumption in bcm per year")+
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 18, 
       height = 10, 
       dpi = 300, 
       filename = "Plots/bar_plot_world_CONS.pdf")

#### Plot for overall production and consumption
plot_data_world %>%
  group_by(Scen, Type, Year) %>%
  summarise(Capacity=sum(Capacity)) %>% 
  ungroup() %>%
  filter(Type != "Trade")%>%
  ggplot(aes(x = Year, y = Capacity, colour = Type, shape = Scen, group = interaction(Type, Scen))) + 
  geom_line(aes(color = Type),size = 1) +
  geom_point(aes(shape = Scen),size = 2) +
  theme_plot+
  scale_colour_manual(values = rep(col_cap, times = 2), 
                      name = "Volume of", 
                      labels=c("consumption", "production")
  ) +
  fonts +
  labs(title = "World outlook on total production and consumption of gas",
       y = "Volume of Gas in bcm") +
  ggsave(width = 18, 
       height = 10, 
       dpi = 300, 
       filename = "Plots/lineplot_world.pdf")

#add interactive map
for (i in number_scenario) {
  a <- dplyr::filter(plot_data_world_2, Scen == i)
  b <- plot_data_world_3
  leaflet() %>%addTiles()%>% 
    addProviderTiles(providers$CartoDB.PositronNoLabels) %>%
    addLabelOnlyMarkers(lng = a$longitude, 
                        lat = a$latitude, 
                        label = a$Region,
                        labelOptions = labelOptions(noHide = TRUE, 
                                                    textOnly = TRUE, 
                                                    direction = "bottom", 
                                                    offset = c(0,-10),
                                                    textsize = 14
                        )
    ) %>% 
    addFlows(
      b$longitude.x,
      b$latitude.x,
      b$longitude.y,
      b$latitude.y,
      color = "#79a2ce",
      #opacity = 0.9,
      maxThickness = 15,
      flow = b$Trade,
      #time = b$Year,
      popup = popupArgs(showTitle = T, 
                        showValues = T, 
                        labels=c("Trade [bcma]"), 
                        digits=2)
    ) %>%
    mapOptions(zoomToLimits = "first") %>%
    addMinicharts(a$longitude, 
                  a$latitude, 
                  type="bar", 
                  colorPalette = col_cap, 
                  time = a$Year,
                  chartdata=a[, c("Prod", "Cons")], 
                  width = 40, height = 120, 
                  popup = popupArgs(showTitle= T, 
                                    showValues = T, 
                                    labels=c("Production [bcma]", "Consumption [bcma]"), 
                                    digits=2
                  )
    ) %>%
  mapshot(url= paste("Plots/world_map_", i, ".html", sep = ""))
}

 
"End of execution. Find plots in folder <Plots>"