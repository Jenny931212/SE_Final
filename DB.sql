--
-- PostgreSQL database dump
--

\restrict Ynq1KpoFYQslYHsuh4VEpFotS3PstqcqwPRzLmPUTDHyhwkd1CLyhQNPZfipyro

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

-- Started on 2025-12-02 18:28:20

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 225 (class 1255 OID 16426)
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END; $$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 224 (class 1259 OID 16454)
-- Name: closure_files; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.closure_files (
    id integer NOT NULL,
    project_id integer NOT NULL,
    contractor_id integer NOT NULL,
    filename character varying(255) NOT NULL,
    filepath character varying(500) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.closure_files OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16453)
-- Name: closure_files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.closure_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.closure_files_id_seq OWNER TO postgres;

--
-- TOC entry 4956 (class 0 OID 0)
-- Dependencies: 223
-- Name: closure_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.closure_files_id_seq OWNED BY public.closure_files.id;


--
-- TOC entry 220 (class 1259 OID 16401)
-- Name: projects; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    description text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    client_id integer NOT NULL,
    contractor_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT projects_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'submitted'::character varying, 'reject'::character varying, 'closed'::character varying])::text[])))
);


ALTER TABLE public.projects OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16400)
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.projects_id_seq OWNER TO postgres;

--
-- TOC entry 4957 (class 0 OID 0)
-- Dependencies: 219
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- TOC entry 222 (class 1259 OID 16429)
-- Name: proposals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.proposals (
    id integer NOT NULL,
    project_id integer NOT NULL,
    contractor_id integer NOT NULL,
    message text NOT NULL,
    price numeric(12,2) NOT NULL,
    accepted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT proposals_price_check CHECK ((price >= (0)::numeric))
);


ALTER TABLE public.proposals OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16428)
-- Name: proposals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.proposals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.proposals_id_seq OWNER TO postgres;

--
-- TOC entry 4958 (class 0 OID 0)
-- Dependencies: 221
-- Name: proposals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.proposals_id_seq OWNED BY public.proposals.id;


--
-- TOC entry 218 (class 1259 OID 16389)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['client'::character varying, 'contractor'::character varying])::text[])))
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 16388)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- TOC entry 4959 (class 0 OID 0)
-- Dependencies: 217
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 4767 (class 2604 OID 16457)
-- Name: closure_files id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.closure_files ALTER COLUMN id SET DEFAULT nextval('public.closure_files_id_seq'::regclass);


--
-- TOC entry 4760 (class 2604 OID 16404)
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- TOC entry 4764 (class 2604 OID 16432)
-- Name: proposals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proposals ALTER COLUMN id SET DEFAULT nextval('public.proposals_id_seq'::regclass);


--
-- TOC entry 4758 (class 2604 OID 16392)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 4950 (class 0 OID 16454)
-- Dependencies: 224
-- Data for Name: closure_files; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.closure_files (id, project_id, contractor_id, filename, filepath, created_at) FROM stdin;
1	1	3	trash.jpg	uploads\\project1_20251022191719_trash.jpg	2025-10-22 19:17:19.128686+08
2	3	2	basketball.jpg	uploads\\project3_20251023152802_basketball.jpg	2025-10-23 15:28:02.486132+08
5	2	2	50嵐.jpg	uploads\\project2_20251102202639_50嵐.jpg	2025-11-02 20:26:39.971533+08
9	7	2	杜拜巧克力.jpg	uploads\\project7_20251104170117_杜拜巧克力.jpg	2025-11-04 17:01:17.335137+08
11	6	3	便當.jpg	uploads\\project6_20251104204849_便當.jpg	2025-11-04 20:48:49.868301+08
13	9	2	OliveYoung.jpg	uploads\\project9_20251105201255_OliveYoung.jpg	2025-11-05 20:12:55.946282+08
\.


--
-- TOC entry 4946 (class 0 OID 16401)
-- Dependencies: 220
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.projects (id, title, description, status, client_id, contractor_id, created_at, updated_at) FROM stdin;
1	幫我倒垃圾	不想出門，請到xxx路xx號幫我倒垃圾	closed	1	3	2025-10-22 16:47:41.360203+08	2025-10-22 19:17:47.80934+08
4	幫我買感冒藥	去xx藥局買xxx，送到xxx路xx號\r\n願意花$1000~~\r\n電話:09263202639	in_progress	1	3	2025-10-27 20:32:07.444014+08	2025-10-27 20:54:41.064063+08
5	幫我去xxx麵包店買鹽可頌	就是那家在xxx路上的，要送到xxx路\r\n願意付跑路費$600\r\n我的電話是0956258986	open	4	\N	2025-10-27 23:25:36.815353+08	2025-10-27 23:25:36.815353+08
3	陪我打籃球	如題 日本岡山xxxx路上的籃球場\r\n給你3000日圓!!\r\n	closed	4	2	2025-10-23 15:01:44.730748+08	2025-11-02 19:14:44.259345+08
2	幫我買飲料	50嵐的波霸奶綠 微糖微冰 謝謝!!\r\n我願意付200元以及飲料本來的$$	closed	1	2	2025-10-22 20:51:51.566174+08	2025-11-02 21:02:07.498821+08
7	杜拜巧克力代購	我想買最近很紅的那個杜拜巧克力\r\n預計給$1000代購費\r\n可以加賴聊!!!\r\n電話:09xxxxxxxx\r\nid:dkjfrlw	closed	5	2	2025-11-04 16:45:30.246787+08	2025-11-04 17:01:36.11374+08
8	買包包	xxxxxxxx哈哈阿	open	6	\N	2025-11-04 20:15:58.073933+08	2025-11-04 20:16:21.410811+08
6	幫我買便當	在附近的再來，我願意付跑腿費$300\r\nxx便當店 豬蹄便當!!\r\n送到xxx路xx號	closed	4	3	2025-10-31 10:52:45.280417+08	2025-11-04 20:49:18.460729+08
9	韓國Olive Young代購	有人近期會去韓國的嗎!!??\r\n可以幫我帶xxx面膜還有xxx護髮素回來嗎?\r\n預計給1000代購費$$\r\n我的聯絡電話是00000\r\n	closed	7	2	2025-11-05 20:08:43.926626+08	2025-11-05 20:13:25.35748+08
\.


--
-- TOC entry 4948 (class 0 OID 16429)
-- Dependencies: 222
-- Data for Name: proposals; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.proposals (id, project_id, contractor_id, message, price, accepted, created_at) FROM stdin;
1	1	2	好的	500.00	f	2025-10-22 17:40:36.387009+08
2	1	3	我家在附近而已 馬上到!!!	350.00	t	2025-10-22 17:43:04.267775+08
3	3	2	我可以哦哦哦哦	600.00	t	2025-10-23 15:06:20.172432+08
4	4	2	沒問題，預計30分鐘後送到，先打電話連絡您~~\r\n我的電話是09365498456	1000.00	f	2025-10-27 20:45:52.455102+08
5	4	3	好!!我在附近!!20分鐘內就到\r\n給我800元就行了~!	800.00	t	2025-10-27 20:48:04.34711+08
6	2	2	好的 20分鐘到	200.00	t	2025-11-02 19:44:51.165098+08
7	7	2	我xxx月預計會去xxx， 可以幫你買~!\r\n我的賴叫做xxx\r\n已加!!	1000.00	t	2025-11-04 16:55:05.984073+08
8	8	2	好	500.00	f	2025-11-04 20:20:27.635858+08
9	6	2	好 我在附近 20分鐘到!!	300.00	f	2025-11-04 20:39:10.102814+08
10	6	3	沒問題 馬上到!!	300.00	t	2025-11-04 20:42:41.555288+08
11	9	2	我下周出差會去!可以幫你代購~!\r\n我的電話是09xxxxxxxxx\r\n	1000.00	t	2025-11-05 20:10:19.491595+08
\.


--
-- TOC entry 4944 (class 0 OID 16389)
-- Dependencies: 218
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, username, password_hash, role, created_at) FROM stdin;
1	Jiayen	$pbkdf2-sha256$29000$LwUA4Jxzbk0JIcTYO2fs/Q$Z4WZSfrWuf9izBLjMlOvLiLc17vQp/OM814l5PE/JkY	client	2025-10-22 16:46:04.058746+08
2	Jiayen(接案版)	$pbkdf2-sha256$29000$AsD4fw8hxPgfA0AIQYjRmg$M9TqHxaDqSvBLmckTyQ6k6qWMQ.VKt1r4FIJ4dsj9jM	contractor	2025-10-22 16:48:51.92849+08
3	Jungwon	$pbkdf2-sha256$29000$L0XIudf6f4/xXouRkpJSyg$LFBfSyX71Kl0shz2Z7GiQXdQ4R62XoSdmbiuBivohA8	contractor	2025-10-22 17:42:16.455506+08
4	niki	$pbkdf2-sha256$29000$cs75H6M05tz7n9M6Z2xNyQ$8SEhP1/RfvyM1ufVwaVKXi04s8RWsvlWS3ho9Gwt.X8	client	2025-10-23 15:00:10.925543+08
5	JW	$pbkdf2-sha256$29000$ivG.NyaE8F5rrVVqLWWsVQ$TtTI8su95w5GVYql0moPXwp5jC/AcDKyBnGYqB1DRmA	client	2025-11-04 16:34:58.678906+08
6	test1	$pbkdf2-sha256$29000$U8oZQwhBaM0ZI4Rw7h0jhA$tWZI1YPn1dpuUGeU2mE0gX6AKFWme5049jVbiKW7IzQ	client	2025-11-04 20:14:49.374576+08
7	Jenny	$pbkdf2-sha256$29000$SSnFuHduzTkHoLQ2xljL.Q$TFIDkm4jZcoTLBffJg9cCnzWG7anK6CkIFaIkGGppnI	client	2025-11-05 20:07:59.068784+08
\.


--
-- TOC entry 4960 (class 0 OID 0)
-- Dependencies: 223
-- Name: closure_files_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.closure_files_id_seq', 13, true);


--
-- TOC entry 4961 (class 0 OID 0)
-- Dependencies: 219
-- Name: projects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.projects_id_seq', 9, true);


--
-- TOC entry 4962 (class 0 OID 0)
-- Dependencies: 221
-- Name: proposals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.proposals_id_seq', 11, true);


--
-- TOC entry 4963 (class 0 OID 0)
-- Dependencies: 217
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 7, true);


--
-- TOC entry 4788 (class 2606 OID 16462)
-- Name: closure_files closure_files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.closure_files
    ADD CONSTRAINT closure_files_pkey PRIMARY KEY (id);


--
-- TOC entry 4781 (class 2606 OID 16412)
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- TOC entry 4786 (class 2606 OID 16439)
-- Name: proposals proposals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proposals
    ADD CONSTRAINT proposals_pkey PRIMARY KEY (id);


--
-- TOC entry 4774 (class 2606 OID 16396)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 4776 (class 2606 OID 16398)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 4789 (class 1259 OID 16474)
-- Name: idx_closure_contractor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_closure_contractor ON public.closure_files USING btree (contractor_id);


--
-- TOC entry 4790 (class 1259 OID 16473)
-- Name: idx_closure_project; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_closure_project ON public.closure_files USING btree (project_id);


--
-- TOC entry 4777 (class 1259 OID 16423)
-- Name: idx_projects_client; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_projects_client ON public.projects USING btree (client_id);


--
-- TOC entry 4778 (class 1259 OID 16424)
-- Name: idx_projects_contractor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_projects_contractor ON public.projects USING btree (contractor_id);


--
-- TOC entry 4779 (class 1259 OID 16425)
-- Name: idx_projects_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_projects_status ON public.projects USING btree (status);


--
-- TOC entry 4782 (class 1259 OID 16452)
-- Name: idx_proposals_accepted; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_proposals_accepted ON public.proposals USING btree (accepted);


--
-- TOC entry 4783 (class 1259 OID 16451)
-- Name: idx_proposals_contractor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_proposals_contractor ON public.proposals USING btree (contractor_id);


--
-- TOC entry 4784 (class 1259 OID 16450)
-- Name: idx_proposals_project; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_proposals_project ON public.proposals USING btree (project_id);


--
-- TOC entry 4772 (class 1259 OID 16399)
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- TOC entry 4797 (class 2620 OID 16427)
-- Name: projects trg_projects_updated; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_projects_updated BEFORE UPDATE ON public.projects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- TOC entry 4795 (class 2606 OID 16468)
-- Name: closure_files closure_files_contractor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.closure_files
    ADD CONSTRAINT closure_files_contractor_id_fkey FOREIGN KEY (contractor_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4796 (class 2606 OID 16463)
-- Name: closure_files closure_files_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.closure_files
    ADD CONSTRAINT closure_files_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4791 (class 2606 OID 16413)
-- Name: projects projects_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 4792 (class 2606 OID 16418)
-- Name: projects projects_contractor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_contractor_id_fkey FOREIGN KEY (contractor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 4793 (class 2606 OID 16445)
-- Name: proposals proposals_contractor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proposals
    ADD CONSTRAINT proposals_contractor_id_fkey FOREIGN KEY (contractor_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4794 (class 2606 OID 16440)
-- Name: proposals proposals_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.proposals
    ADD CONSTRAINT proposals_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


-- Completed on 2025-12-02 18:28:20

--
-- PostgreSQL database dump complete
--

\unrestrict Ynq1KpoFYQslYHsuh4VEpFotS3PstqcqwPRzLmPUTDHyhwkd1CLyhQNPZfipyro

