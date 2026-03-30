###############################################################################
#                                                                             #
#       This code prepares the Global Gas Model's output by GAMS for          #
#         visualisation of the results in plots and interactive maps          #
#                                                                             #
###############################################################################

# run the whole script with Ctrl + Alt + R

# saves packages in a vector
data_packages <- c(
  "dplyr", "tidyr", "leaflet", 
  "leaflet.extras", "leaflet.minicharts", 
  "ggplot2", "tidyverse", "mapview", "webshot"
)

# function to load required packages
check_packages <- lapply(data_packages, FUN = function(x) {
  if (!require(x, character.only = TRUE)) {
    install.packages(x, dependencies = TRUE)
    library(x, character.only = TRUE)
  }
})

# remove information for packages
rm(data_packages)
rm(check_packages)


############################### RAW DATA ######################################

# load data from GAMS output for consumption and production
raw_data <- read.csv(
  "rep_geo_map_SDS.csv",         # name of the file
  header = T,
  stringsAsFactors = F, 
  skip = 1,                   # first line is skipped
  sep = ","                   # declaration of separator
  ) %>% 
  # deletes all columns with aggregate capacities
  dplyr::select(-starts_with("expcum")) %>%
  # appends rows from other scenarios (DUPLICATE/REMOVE)
  bind_rows(                      # can be removed or duplicated
    read.csv(
      "rep_geo_map_NPS.csv",      # name of the file
      header = T,
      stringsAsFactors = F, 
      skip = 1,                   # first line is skipped
      sep = ","                   # declaration of separator
    ) %>% 
      dplyr::select(-starts_with("expcum"))
  ) %>%
  # substitutes all NAs with 0
  mutate_all(list(~replace(., is.na(.), 0))) %>%
  dplyr::filter(X != "")
  

# load data from GAMS output for trade flows between regions
raw_data2 <- read.csv(
  "rep_geo_map_SDS_flow.csv",     # name of the file
  header = T,
  stringsAsFactors = F, 
  sep = ","                   # declaration of separator
  ) %>%
  # appends rows from other scenarios (DUPLICATE/REMOVE)
  bind_rows(                      # can be removed or duplicated
    read.csv(
      "rep_geo_map_NPS_flow.csv",      # name of the file
      header = T,
      stringsAsFactors = F, 
      sep = ","                   # declaration of separator
    )
  ) %>%
  #substitutes all NAs with 0
  mutate_all(list(~replace(., is.na(.), 0))) %>%
  dplyr::filter(X != "")

# defines a function to create a vector for the column names
naming <- function(x,y,yy){
  a <- x
  b <- y
  while(b <= yy){
    if(b == y){
      a <- paste(x,y, sep="_")
      b <- b+5
    } else{
      a <- c(a, paste(x,b, sep="_"))
      b <- b+5} 
  }
  return(a)
}

# define column name vector, change here if vector should look different
columnnames <- c(       # this can look different if GAMS report changes
  "Cons", 
  "Prod", 
  "Trade", 
  "LNG", 
  "Pipe", 
  "Exp-P+", 
  "Exp-P-", 
  "Exp-L", 
  "Exp-R", 
  "Exp-Stor") %>%
  #NUMBER OF YEARS MUST BE ADJUSTED HERE! naming(start-year, end-year)
  naming(2015, 2050)    # define time horizon of GAMS report

# adds the fist two columnnames that stand for region and country
columnnames1 <- c(
  "Scen","RGN", "CN",   # names of the first three columns
  columnnames           
  )  

# changes the columnnames to the created vector
names(raw_data) <- columnnames1


# creates vector with columnnames for trade data
columnnames_flow <- c("Trade") %>% 
  naming(2015, 2050)                  # define time horizon

# adds the first six columns
columnnames2 <- c(
  "Scen","RGN", "CN", "RGN1", "CN1",  # could change
  columnnames_flow
  )

# changes the columnnames to the created vector
names(raw_data2) <- columnnames2

# saves the names of the Scenarios in one vector
number_scenario <- as.vector(t(unique(raw_data$Scen)))
number_scenario2 <- as.vector(t(unique(raw_data2$Scen)))

number_scenario == number_scenario2  # if false: THERE IS AN ERROR


# defines full region names
regions <- data.frame(       # might change if GGM regions change
  c(
    "SAM", "NAM", "EU", 
    "ROE", "AFR", "ASP", 
    "MEA", "CAS", "RUS", "NOR"
    ),
  c(
    "South America",
    "North America", 
    "European Union",
    "Rest of Europe",
    "Africa", 
    "Asia Pacific",
    "Middle East Asia",
    "Caspian Region",
    "Russia", "Norway"
    ), 
  stringsAsFactors = FALSE
  ) 
# adds colum names to the dataframe
names(regions) <- c("RGN", "Region")

# creates a vector of colours
coloring <- c(               # change for other colours
  "#00509e", #NTNU blue 
  "#f1d282", #beige
  "#5cbec9", #turquoise
  "#d5d10e", #green-yellow
  "#79a2ce", #blue
  "#f58025", #orange
  "#c9d4b2", #green
  "#dde7ee", #lightblue
  "#552988", #purple
  "#404040"  #grey
)

# defines a function that multiplies objects by -1
opposite <- function(x){ x*(-1)}


save(raw_data, raw_data2, file="raw_data.RData")


############################### EUROPE ########################################


#data load for geographical data for Europe
# DON'T CHANGE
geo_data_EU <- read.csv(
  "countries_middle_lat_lon.csv", 
  header = TRUE, 
  stringsAsFactors = FALSE, sep=","
  ) %>% 
  rename(iso2=ï..country) %>% 
  transform(
    latitude = as.numeric(latitude), 
    longitude = as.numeric(longitude)
    )

# adjust data for bar plots
plot_data_EU <- raw_data %>%
  # filters for region EU and rest of Europe (ROE)
  filter(RGN=="EU" | RGN== "ROE" | RGN == "NOR") %>%
  # selects data on consumption, production 
  dplyr::select(               # adjust selection for different graphs
    1:3, 
    starts_with("Cons"), 
    starts_with("Prod")
    ) %>%
  # joins data with geo_data to include full country names
  left_join(geo_data_EU, by="CN")%>%
  # rearranges table so the capacities are gathered in one 
  # column and specifies in another column 
  # CHECK length minus 4
  gather("Type", "Capacity", 4:(length(.)-4))%>% 
  # separation of capacity type into Type and Year
  separate(Type, into=c("Type", "Year"), sep = "_")

map_countries <- t(spread(
  plot_data_EU, Type, Capacity
  ) %>%
  filter(Year == "2015") %>%
  filter(Cons > 10.0 | Prod > 5.0) %>%
  dplyr::select("name") %>%
  distinct())

# data for interactive maps
plot_data_EU_2 <- spread(
  plot_data_EU, Type, Capacity
  ) %>%
  filter(name %in% map_countries)      # adjust for other countries on maps
 
# saves data frames in a workspace
save(
  coloring, 
  plot_data_EU, 
  plot_data_EU_2, 
  opposite, 
  number_scenario, 
  file="data_EU.RData"
  )

# removes working environment
rm(columnnames)
rm(columnnames1)
rm(columnnames2)
rm(columnnames_flow)
rm(naming)


############################### WORLD REGIONS #################################

# data load for geographical data 
geo_data_world <- read.csv2(
  "geo_data.csv", header=TRUE, 
  stringsAsFactors = FALSE
  ) %>% 
  transform(
    latitude= as.numeric(latitude), 
    longitude=as.numeric(longitude)
    ) %>%
  group_by(RGN) %>%
  summarise_at(vars(-(1:2)), mean) %>% 
  bind_rows(filter(geo_data_EU, name == "Norway")) %>%
  select(1:3) %>%
  replace(is.na(.), "NOR")

# adjusts geographical data
geo_data_world$longitude[
  geo_data_world$RGN == "EU"] <- geo_data_world$longitude[
    geo_data_world$RGN == "EU"] - 12
geo_data_world$longitude[
  geo_data_world$RGN == "ROE"] <- geo_data_EU$longitude[
    geo_data_EU$name == "Turkey"]
geo_data_world$latitude[
  geo_data_world$RGN == "ROE"] <- geo_data_EU$latitude[
    geo_data_EU$name == "Turkey"]
geo_data_world$latitude[
  geo_data_world$RGN == "CAS"] <- geo_data_world$latitude[
    geo_data_world$RGN == "CAS"] + 8
geo_data_world$latitude[
  geo_data_world$RGN == "MEA"] <- geo_data_world$latitude[
    geo_data_world$RGN == "MEA"] - 3
geo_data_world$latitude[
  geo_data_world$RGN == "ASP"] <- geo_data_world$latitude[
    geo_data_world$RGN == "ASP"] - 8


# adjust data for bar plots
plot_data_world <- raw_data %>%
  # remove rows for regasification and liquefaction
  dplyr::filter(RGN != "LIQ" & RGN != "REG") %>%
  # selects data on consumption, production 
  dplyr::select(                        # adjust for other data
    1:2, 
    starts_with("Cons"), 
    starts_with("Prod")
    ) %>%
  # aggregates values for different regions 
  group_by(Scen, RGN) %>%
  summarise_all(funs(sum)) %>%
  ungroup() %>%
  # join with geo data
  left_join(geo_data_world, by="RGN") %>%
  # rearranges table so the capacities are gathered in one column and 
  # specifies in another column
  gather("Type", "Capacity", 3:(length(.)-2)) %>% 
  # separation of capacity type into Type and Year
  separate(Type, into=c("Type", "Year"), sep = "_") %>%
   left_join(regions, by= "RGN")

# data frame for interactive maps
plot_data_world_2 <- spread(
  plot_data_world, Type, Capacity
  )

# data frame for trade flows
plot_data_world_3 <- raw_data2 %>%
  # remove rows for regasification and liquefaction
  dplyr::filter(
    RGN != "LIQ" & 
      RGN != "REG" & 
      CN != CN1 & 
      RGN1 != "LIQ" & 
      RGN1 != "REG"  & 
      RGN != RGN1
    ) %>%
  # removes country codes
  dplyr::select(- starts_with("CN")) %>%
  # aggregation of data over regions
  group_by(Scen, RGN, RGN1) %>%
  summarise_all(funs(sum)) %>%
  ungroup() %>% 
  # adding geographical data to dataframe
  left_join(geo_data_world, by = "RGN") %>%
  left_join(geo_data_world, by = c("RGN1" = "RGN")) %>%
  # gathering capacities
  gather("Type", "Capacity", 4:(length(.)-4)) %>%
  # separate year and type
  separate(Type, into=c("Type", "Year"), sep = "_") %>%
  # build column of type and capacity
  spread(Type, Capacity) %>%
  mutate_at(vars(Trade),list(~replace(., Trade < 20, 0))) %>%
  group_by(Scen, RGN, RGN1, longitude.x, latitude.x, longitude.y, latitude.x) %>%
  filter(sum(Trade) != 0 ) %>% 
  ungroup()

# save data frame in workspace
save(
  coloring, 
  plot_data_world, 
  plot_data_world_2, 
  plot_data_world_3, 
  number_scenario, 
  file="data_world.RData"
  )

# remove working files
rm(raw_data)
rm(raw_data2)
rm(number_scenario)

"End of execution. Execution successful"
