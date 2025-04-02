import time
import random
import requests
import pandas as pd
import os
from bs4 import BeautifulSoup as bs
from fake_useragent import UserAgent


class ScraperO1(object):
    def __init__(self, page=1, city=None):
        if not isinstance(page, int) or page <= 0:
            raise ValueError(f"{page} must be an integer number greater than 0")

        if city is None:
            raise ValueError("Parameter city missing, please select a city")

        if not isinstance(city, str):
            raise ValueError(f"{city} must be a string")

        self.pages = page
        # Sostituisce gli spazi con '-'
        self.cities = city.replace(" ", "-")

        # Sessione persistente
        self.session = requests.Session()

        # Inizializzazione di fake_useragent
        self.ua = UserAgent()

        # Alcune versioni dell’UA (desktop + mobile) per maggiore varietà
        self.user_agents_pool = [
            self.ua.chrome, self.ua.firefox, self.ua.ie,
            self.ua.safari, self.ua.opera, self.ua.edge,
            self.ua.android, self.ua.iphone
        ]

    def get_random_user_agent(self):
        """Restituisce un User-Agent a caso dalla pool."""
        return random.choice(self.user_agents_pool)

    def get_soup(self, url):
        """Scarica e restituisce il soup della pagina, con rotazione UA e gestione sessione."""

        if not isinstance(url, str):
            raise ValueError(f"{url} deve essere una stringa.")

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"{url} deve iniziare con 'http://' o 'https://'.")

        max_attempts = 30
        attempts = 0

        while attempts < max_attempts:
            try:
                # Pausa casuale breve
                time.sleep(random.uniform(1, 3))

                headers = {
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0",
                    "Referer": "https://www.google.com/"
                }

                response = self.session.get(url, headers=headers, timeout=10)

                # Se c’è una pagina di check/captcha, usciamo
                if "verifica che non sei un robot" in response.text.lower() or "captcha" in response.text.lower():
                    print(f"[CAPTCHA/Redirect] Rilevato su {url}. Skip pagina.")
                    return None

                if response.status_code == 200:
                    # Leggero sleep dopo la risposta
                    time.sleep(random.uniform(0.5, 1.5))
                    return bs(response.text, "html.parser")
                else:
                    attempts += 1
                    # piccola pausa e ritenta
                    time.sleep(2)

            except requests.exceptions.RequestException as e:
                attempts += 1
                time.sleep(2)

        # Se siamo arrivati qui, significa che i tentativi sono falliti.
        return None

    def max_page(self):
        """Determina quante pagine massime sono disponibili per la città indicata."""
        start_link = f"https://www.immobiliare.it/vendita-case/{self.cities}/"
        get_max_page = self.get_soup(start_link)

        if get_max_page is None:
            print(f"Impossibile caricare la pagina {start_link}, si assume max_page = 1.")
            return 1

        pagination_list = get_max_page.find("div", {"data-cy": "pagination-list"})
        if pagination_list is None:
            return 1
        else:
            disabled_items = pagination_list.find_all(
                "div",
                class_="nd-button nd-button--ghost is-disabled in-paginationItem is-mobileHidden"
            )
            if not disabled_items:
                return 1
            max_page = int(disabled_items[-1].get_text(strip=True))
        return max_page

    def get_links(self):
        """Genera l'elenco randomizzato di link di listing (pagine 1..N in ordine casuale)."""
        # Trova la max page effettiva
        max_page = self.max_page()

        if self.pages > max_page:
            raise ValueError(
                f"Total number of pages richieste ({self.pages}) maggiore delle disponibili: {max_page}"
            )

        # Genera la lista di pagine
        pages_list = list(range(1, self.pages + 1))
        # Shuffle per randomizzazione
        random.shuffle(pages_list)

        lst_links = [
            f"https://www.immobiliare.it/vendita-case/{self.cities}/?pag={page}#geohash-srbj60jf"
            for page in pages_list
        ]

        # Estrae i link effettivi degli annunci
        all_annunci_links = []
        for idx, str_link in enumerate(lst_links, start=1):
            # Pausa random prima di chiamare get_soup
            time.sleep(random.uniform(1, 3))

            # Ogni tot richieste, pausa più lunga
            if idx % random.randint(6, 10) == 0:
                time.sleep(random.uniform(5, 10))

            soup_link = self.get_soup(str_link)
            if soup_link is None:
                print(f"Non è stato possibile accedere a {str_link}. Link saltato.")
                continue

            found_listing_cards = soup_link.find_all("a", class_="in-listingCardTitle")
            links_on_page = [a_tag["href"] for a_tag in found_listing_cards]
            all_annunci_links.extend(links_on_page)

        return all_annunci_links

    @staticmethod
    def sec_feat(soup):
        """Estrae caratteristiche secondarie standard dell'annuncio."""
        dct_tmp = dict()
        tmp_lst = [
            "Tipologia", "Piano", "Ascensore", "Locali", "Cucina", "Arredato",
            "Terrazzo", "Contratto", "Piani edificio", "Superficie",
            "Camere da letto", "Bagni", "Balcone", "Box, posti auto",
            "Prezzo", "Prezzo al m²", "Spese condominio"
        ]
        for item in tmp_lst:
            dt = soup.find("dt", class_="ld-featuresItem__title", string=item)
            if dt:
                dd = dt.find_next_sibling("dd", class_="ld-featuresItem__description")
                value = dd.get_text(strip=True) if dd else None
            else:
                value = None
            dct_tmp[item] = value

        return dct_tmp

    def prc_feat(self, soup):
        """Placeholder per estrarre eventuali altre info personalizzate."""
        # Se hai logica specifica, mettila qui.
        return {}

    def scraping(self):
        csv_filename = "immobiliare.csv"
        link_list = self.get_links()
        total_links = len(link_list)

        all_data = []

        for i, link in enumerate(link_list, 1):
            # Pausa random fra una pagina e l’altra
            time.sleep(random.uniform(1, 3))

            # Ogni tot richieste, pausa più lunga random
            if i % random.randint(6, 10) == 0:
                time.sleep(random.uniform(5, 10))

            soup = self.get_soup(link)
            if soup is None:
                print(f"Non è stato possibile accedere al dettaglio {link}. Link saltato.")
                continue

            dct_tmp = {"url": link}

            try:
                # Logica personalizzata
                dct_prc = self.prc_feat(soup)
                dct_tmp.update(dct_prc)

                # Se "Unità" è presente, saltiamo
                scrape_filter = soup.find("dt", class_="ld-featuresItem__title", string="Unità")
                if scrape_filter is not None:
                    print(f"Under-construction apartment, non valido {i} / {total_links}")
                    continue

                dct_sec = self.sec_feat(soup)
                dct_tmp.update(dct_sec)

                all_data.append(dct_tmp)

                # Salvataggio intermedio su CSV in append
                df_temp = pd.DataFrame([dct_tmp])
                write_header = not os.path.exists(csv_filename)
                df_temp.to_csv(csv_filename, mode='a', header=write_header, index=False)

                print(f"Scrap OK {i} / {total_links}")

            except Exception as e:
                print(f"Errore durante lo scraping del link {link}: {e}")

        # Al termine, restituisce un DataFrame completo
        df_final = pd.DataFrame(all_data)
        return df_final


if __name__ == "__main__":
    scraper = ScraperO1(page=80, city="bologna")
    df = scraper.scraping()
    print(df)
    # Salvataggio finale
    df.to_csv("immobiliare2.csv", index=False)
    print("File salvato come immobiliare2.csv (scrittura finale).")
