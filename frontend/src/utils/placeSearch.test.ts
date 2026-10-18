import { describe, expect, it } from 'vitest';
import { fold, looksLikeAddress, matchScore, searchRows, words, type PlaceRow } from './placeSearch';
import places from '../data/places.json';

// Same cases as algorithms/test_place_search.py: the two twins must agree.
describe('placeSearch', () => {
  it('folds case and Polish accents', () => {
    expect(fold('  Łódź-Kaliska ')).toBe('lodz kaliska');
  });

  it('splits letters, digits and punctuation into words', () => {
    expect(words('DS2 UW')).toEqual(['ds', '2', 'uw']);
    expect(words('Os.Ługi')).toEqual(['os', 'lugi']);
  });

  it('ranks the whole name, the start, whole words, word starts and the inside in this order', () => {
    expect(matchScore('Centrum', 'Centrum')).toBe(0);
    expect(matchScore('cent', 'Centrum')).toBe(1);
    expect(matchScore('metro pol', 'Metro Politechnika')).toBe(1);
    expect(matchScore('politechnika metro', 'Metro Politechnika')).toBe(2);
    expect(matchScore('politechn', 'Metro Politechnika')).toBe(3);
    expect(matchScore('echni', 'Metro Politechnika')).toBe(4);
    expect(matchScore('xyz', 'Metro Politechnika')).toBeNull();
    expect(matchScore('', 'Centrum')).toBeNull();
  });

  it('matches abbreviations both ways', () => {
    expect(matchScore('plac zbawiciela', 'Pl. Zbawiciela')).toBe(1);
    expect(matchScore('pl. zbawiciela', 'Pl. Zbawiciela')).toBe(0);
    expect(matchScore('dworzec centralny', 'Dw. Centralny')).toBe(1);
    expect(matchScore('ds riviera', 'Dom Studenta Riviera')).toBe(1);
    expect(matchScore('osiedle kabaty', 'Os. Kabaty')).toBe(1);
    expect(matchScore('aleje jerozolimskie', 'Al. Jerozolimskie')).toBe(2);
    expect(matchScore('uniwersytet warszawski', 'Kampus Ochota UW')).toBe(2);
    expect(matchScore('pw', 'Gmach Główny Politechniki Warszawskiej')).toBe(2);
  });

  it('treats numbers as whole words and ignores "nr"', () => {
    expect(matchScore('Dom Studenta nr 2', 'DS 2 UW')).toBe(1);
    expect(matchScore('studenta 2', 'DS 2 UW')).toBe(2);
    expect(matchScore('DS2', 'DS 2 UW')).toBe(1);
    expect(matchScore('ds 2', 'DS 21')).toBeNull();
    expect(matchScore('ul. Marszałkowska', 'Marszałkowska')).toBe(0);
  });

  it('matches aliases like the name', () => {
    expect(matchScore('PKiN', 'Pałac Kultury i Nauki', ['PKiN'])).toBe(0);
  });

  it('recognises street addresses', () => {
    expect(looksLikeAddress('Marszałkowska 1')).toBe(true);
    expect(looksLikeAddress('nowy świat 15')).toBe(true);
    expect(looksLikeAddress('Grójecka 17/19')).toBe(true);
    expect(looksLikeAddress('al. Jana Pawła II 82a')).toBe(true);
    expect(looksLikeAddress('Dom Studenta nr 2')).toBe(false);
    expect(looksLikeAddress('ds 2')).toBe(false);
    expect(looksLikeAddress('DS2')).toBe(false);
    expect(looksLikeAddress('Al. 3 Maja')).toBe(false);
  });

  const rows: PlaceRow[] = [
    ['Stacja Centrum', 52.2, 21.0, 0],
    ['Centrum Nauki', 52.2, 21.0, 1],
    ['Centrum', 52.2, 21.0, 0],
  ];

  it('puts better matches first and labels the kind', () => {
    const found = searchRows(rows, 'centrum');
    expect(found.map((p) => p.label)).toEqual(['Centrum', 'Centrum Nauki', 'Stacja Centrum']);
    expect(found[1].sublabel).toBe('Stacja Veturilo');
    expect(found[0].sublabel).toBe('Przystanek');
  });

  it('puts well-known places before stops of the same quality', () => {
    const mixed: PlaceRow[] = [
      ['Arkadia', 52.2, 21.0, 1],
      ['Westfield Arkadia', 52.2, 21.0, 2, 'Centrum handlowe', ['Arkadia']],
    ];
    const found = searchRows(mixed, 'arkadia');
    expect(found.map((p) => p.label)).toEqual(['Westfield Arkadia', 'Arkadia']);
    expect(found[0].sublabel).toBe('Centrum handlowe');
  });

  it('orders equal matches by distance from the user', () => {
    const near: PlaceRow[] = [['Wilanowska', 52.17, 21.03, 0], ['Wilanowska', 52.23, 21.0, 0]];
    expect(searchRows(near, 'wilan', 4, [52.231, 21.0])[0].position[0]).toBe(52.23);
  });
});

describe('the bundled list answers the user test list', () => {
  const all = places as PlaceRow[];
  const first = (q: string) => searchRows(all, q, 5, [52.23, 21.01])[0]?.label;

  it.each([
    ['ds 2 uw', 'DS 2 UW'],
    ['Dom Studenta nr 2', 'DS 2 UW'],
    ['DS2', 'DS 2 UW'],
    ['pl. zbawiciela', 'Pl. Zbawiciela'],
    ['plac Zbawiciela', 'Plac Zbawiciela'],
    ['metro centrum', 'Metro Centrum'],
    ['centrum nauki kopernik', 'Centrum Nauki Kopernik'],
    ['kopernik', 'Centrum Nauki Kopernik'],
    ['PKiN', 'Pałac Kultury i Nauki'],
    ['pałac kultury', 'Pałac Kultury i Nauki'],
    ['palac kultury', 'Pałac Kultury i Nauki'],
    ['uw', 'Uniwersytet Warszawski'],
    ['politechnika', 'Politechnika'],
    ['PW', 'Politechnika Warszawska'],
    ['dw. centralny', 'Warszawa Centralna'],
    ['dworzec centralny', 'Warszawa Centralna'],
    ['Warszawa Centralna', 'Warszawa Centralna'],
    ['galeria mokotów', 'Westfield Mokotów'],
    ['galeria mokotow', 'Westfield Mokotów'],
    ['arkadia', 'Westfield Arkadia'],
    ['lotnisko', 'Lotnisko Chopina'],
    ['chopin', 'Lotnisko Chopina'],
  ])('%s -> %s', (query, expected) => {
    expect(first(query)).toBe(expected);
  });

  it('finds both spellings of a stop', () => {
    const labels = searchRows(all, 'zbawiciela', 5).map((p) => p.label);
    expect(labels).toEqual(expect.arrayContaining(['Pl. Zbawiciela', 'Plac Zbawiciela']));
  });

  it.each(['Marszałkowska 1', 'nowy świat 15', 'nowy swiat 15'])('leaves the address %s to Nominatim', (query) => {
    expect(searchRows(all, query, 5)).toEqual([]);
  });

  it('is fast once the list is prepared', () => {
    searchRows(all, 'warm up');
    const t = performance.now();
    for (let i = 0; i < 10; i++) searchRows(all, `galeria ${i}`);
    expect((performance.now() - t) / 10).toBeLessThan(50);
  });
});
