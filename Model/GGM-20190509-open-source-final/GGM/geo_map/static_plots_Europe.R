# Check packages

data_packages <- c(
  "dplyr", "tidyr", "leaflet", 
  "leaflet.extras", "leaflet.minicharts", 
  "mapview", "webshot", "ggplot2", "tidyverse"
)

# Funktion, die Packages installiert und lädt, falls sie das noch nicht sind
check_packages <- lapply(data_packages, FUN = function(x) {
  if (!require(x, character.only = TRUE)) {
    install.packages(x, dependencies = TRUE)
    library(x, character.only = TRUE)
  }
})


# Load data
load("data_EU.RData")
load("layoutPlot.RData")

# make plots for production

# EU 
ggplot(data = filter(
  plot_data_EU, 
  Type == "Prod" & Capacity > 0 & RGN == "EU" &
    Year %in% c("2015", "2030", "2050") 
), 
aes(reorder(name, Capacity), y = Capacity, fill = Scen))+
  geom_bar(stat = "identity", position = "dodge", width = 1) + 
  scale_fill_manual(values = coloring, 
                    name = "Scenario"
  ) +
  theme_plot +
  coord_flip() + 
  labs(title="Gas Production pattern for European Union in two scenarios", 
       x = "Country", 
       y = "Production in bcm per year")+
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 18, 
         height = 10, 
         dpi = 300, 
         filename = "Plots/bar_plot_EU_PROD.pdf")

# ROE
ggplot(data = filter(
  plot_data_EU, 
  Type == "Prod" & Capacity > 0 & RGN %in% c("NOR", "ROE") &
    Year %in% c("2015", "2030", "2050") 
), 
aes(reorder(name, Capacity), y = Capacity, fill = Scen))+
  geom_bar(stat = "identity", position = "dodge", width = 1) + 
  scale_fill_manual(values=coloring, 
                    name= "Scenario"
  ) +
  theme_plot +
  coord_flip() + 
  labs(title ="Gas production pattern for Rest of Europe in two scenarios", 
       x = "Country", 
       y = "Production in bcm per year") +
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 16, 
         height = 7, 
         dpi = 300, 
         filename = "Plots/bar_plot_ROE_PROD.pdf")

# make plot for Consumption

#EU
ggplot(data = filter(
  plot_data_EU, 
  Type == "Cons" & RGN == "EU" &
    Year %in% c("2015", "2030", "2050") 
  ), 
         aes(reorder(name, Capacity), y = Capacity, fill = Scen))+
  geom_bar(stat = "identity", position = "dodge", width = 1) + 
  scale_fill_manual(values = coloring, 
                    name = "Scenario"
  ) +
  theme_plot +
  coord_flip() + 
  labs(title="Gas consumption pattern for European Union in two scenarios", 
       x = "Country", 
       y = "Consumption in bcm per year")+
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 18, 
         height = 10, 
         dpi = 300, 
         filename = "Plots/bar_plot_EU_CONS.pdf")

#EU TOP 10
top10 <- t(plot_data_EU %>% 
  filter(Type == "Cons" & RGN == "EU" & Year == "2015" & Scen == "NPS-Ref") %>%
  arrange(desc(Capacity)) %>% 
  top_n(10)%>%
  select(name))
  
  

ggplot(data = filter(
  plot_data_EU, 
  Type == "Cons" & RGN == "EU" & 
    Year %in% c("2015", "2030", "2050") 
  ) %>% 
    filter(name %in% top10), 
       aes(reorder(name, Capacity), y = Capacity, fill = Scen))+
  geom_bar(stat = "identity", position = "dodge", width = 1) + 
  scale_fill_manual(values = coloring, 
                    name = "Scenario"
  ) +
  theme_plot +
  coord_flip() + 
  labs(title = "Gas consumption pattern for EU Top 10 in two scenarios", 
       x = "Country", 
       y = "Consumption in bcm per year")+
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 18, 
         height = 10, 
         dpi = 300, 
         filename = "Plots/bar_plot_EU10_CONS.pdf")

# ROE
ggplot(data=filter(
  plot_data_EU, 
  Type == "Cons" & RGN %in% c("NOR", "ROE") &
    Year %in% c("2015", "2030", "2050")  
  ), 
       aes(reorder(name, Capacity), y = Capacity, fill = Scen))+
  geom_bar(stat = "identity", position = "dodge", width = 1) + 
  scale_fill_manual(values=coloring, 
                    name= "Scenario"
  ) +
  theme_plot +
  coord_flip() + 
  labs(title ="Gas consumption pattern for Rest of Europe in two scenarios", 
       x = "Country", 
       y = "Consumption in bcm per year") +
  fonts +
  facet_wrap(~Year) +
  ggsave(width = 18, 
         height = 10, 
         dpi = 300, 
         filename = "Plots/bar_plot_ROE_CONS.pdf")


#### Plot for overall production and consumption
plot_data_EU %>%
  group_by(Scen, Type, Year) %>%
  summarise(Capacity = sum(Capacity)) %>% 
  ungroup() %>%
  filter(Type != "Trade") %>%
  ggplot(aes(
    x = Year, y = Capacity, 
    colour = Type, shape = Scen, 
    group = interaction(Type, Scen))
    ) + 
  geom_line(aes(color = Type), size = 1) +
  geom_point(aes(shape = Scen), size = 3) +
  theme_plot +
  scale_colour_manual(values = rep(col_cap, times = 2), 
                      name = "Volume of",
                      labels=c("consumption", "production")
  ) +
  fonts +
  labs(title = "Europe outlook on total production and consumption of gas",
       y = "Volume of Gas in bcm",
       shape = "Scenario"
       ) +
  ylim(0,700) +
  ggsave( width = 18, 
       height = 10, 
       dpi = 300, 
       filename = "Plots/lineplot_EU.pdf")


#add interactive map
for (i in number_scenario) {
  a <- dplyr::filter(plot_data_EU_2, Scen == i)
leaflet() %>%addTiles()%>% 
  addProviderTiles(providers$CartoDB.PositronNoLabels) %>%
  addLabelOnlyMarkers(lng = a$longitude, 
                      lat = a$latitude, 
                      label = a$name,
                      labelOptions = labelOptions(noHide = TRUE, 
                                                  textOnly = TRUE, 
                                                  direction = "bottom", 
                                                  offset = c(0,-10),
                                                  textsize = 14)) %>%
  mapOptions(zoomToLimits = "first") %>%
  addMinicharts(a$longitude, 
                a$latitude, 
                type = "bar", 
                colorPalette = col_cap,
                time = a$Year,
                chartdata = a[, c("Prod", "Cons")], 
                width = 40, height = 160, 
                popup = popupArgs(showTitle=T, 
                                  showValues = T, 
                                  labels=c("Production [bcma]", "Consumption [bcma]"), 
                                  digits=2
                                  )
                ) %>% 
  mapshot(url = paste("Plots/europe_map_", i, ".html", sep = ""))
}


"End of execution. Find plots in folder <Plots>"