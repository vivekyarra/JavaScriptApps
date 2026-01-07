// Movie database
const movies = {
  akhanda2: {
    name: "Akhanda 2",
    actor: "Nandamuri Balakrishna (NBK)",
    director: "Boyapati Srinu",
  },
  devara: {
    name: "Devara",
    actor: "N. T. Rama Rao Jr (NTR)",
    director: "Koratala Siva",
  },
};

// Take input from user
const movieName = prompt("Enter movie name:").toLowerCase().replace(/\s+/g, "");

// Check and display movie info
if (movies[movieName]) {
  console.log("Movie Name:", movies[movieName].name);
  console.log("Actor:", movies[movieName].actor);
  console.log("Director:", movies[movieName].director);
} else {
  console.log("Movie not found in database.");
}
