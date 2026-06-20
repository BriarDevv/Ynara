// Declaración de módulos de assets para import estático (Metro los resuelve a un
// id de asset = number, que `Image source` acepta). expo/types no la trae en
// este tsconfig, así que la declaramos acá.
declare module "*.png" {
  const content: number;
  export default content;
}
